#!/usr/bin/env python3
"""Compile the CV and synchronize publication/news sections using only stdlib."""
import argparse
import calendar
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd=ROOT, env=None):
    print('+', shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def group(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != '{':
        raise ValueError('Expected a braced LaTeX argument')
    start, depth = pos + 1, 1
    pos += 1
    while pos < len(text):
        if text[pos] == '\\':
            pos += 2
            continue
        if text[pos] == '{':
            depth += 1
        elif text[pos] == '}':
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    raise ValueError('Unclosed LaTeX argument')


def url(value):
    if urlparse(value).scheme not in ('https', 'http'):
        raise ValueError('Website links must use http(s): ' + value)
    return html.escape(value, quote=True)


def tex_html(text):
    """Render the small, explicit subset of LaTeX used by CV entries."""
    output, pos = [], 0
    while pos < len(text):
        char = text[pos]
        if char == '\\':
            match = re.match(r'\\([a-zA-Z]+|.)', text[pos:])
            command = match[1]
            pos += len(match[0])
            if command in ('textbf', 'textit', 'mbox', 'emph'):
                content, pos = group(text, pos)
                rendered = tex_html(content)
                tag = {'textbf': 'strong', 'textit': 'em', 'emph': 'em'}.get(command)
                output.append(f'<{tag}>{rendered}</{tag}>' if tag else rendered)
            elif command in ('&', '%', '_', '#', '$', '{', '}'):
                output.append(html.escape(command))
            else:
                raise ValueError(f'Unsupported LaTeX command in publication: \\{command}')
        elif char == '{':
            content, pos = group(text, pos)
            output.append(tex_html(content))
        else:
            output.append(html.escape(' ' if char == '~' else char))
            pos += 1
    return re.sub(r'\s+', ' ', ''.join(output)).strip()


def publications(source):
    body = source.split(r'\begin{document}', 1)[1]
    # Retain metadata separately, then remove TeX comments from actual arguments.
    metadata = []
    lines = []
    for line in body.splitlines():
        if line.startswith('% website-news: '):
            metadata.append((len('\n'.join(lines)), json.loads(line.split(': ', 1)[1])))
        line = re.split(r'(?<!\\)%', line, maxsplit=1)[0]
        lines.append(line)
    body = '\n'.join(lines)
    entries = []
    for match in re.finditer(r'\\publication\s*(?=\{)', body):
        args, pos = [], match.end()
        for _ in range(4):
            arg, pos = group(body, pos)
            args.append(arg)
        title, authors, venue, link = args
        year = re.search(r'\b(20\d{2})\b', venue)
        if not year:
            raise ValueError('Publication venue needs a year: ' + venue)
        paper_url = None
        if link.strip():
            link = link.strip()
            if not link.startswith(r'\href'):
                raise ValueError('Publication link must use \\href')
            paper_url, end = group(link, len(r'\href'))
            _, end = group(link, end)
            if link[end:].strip():
                raise ValueError('Unexpected publication link content')
            url(paper_url)
        news = None
        while metadata and metadata[0][0] <= match.start():
            if news is not None:
                raise ValueError('Multiple news annotations for one publication')
            news = metadata.pop(0)[1]
        entries.append(dict(title=tex_html(title), authors=tex_html(authors),
                            venue=tex_html(venue), year=int(year[1]), url=paper_url, news=news))
    if not entries or metadata:
        raise ValueError('Missing publications or unattached news annotation')
    return entries


def publication_html(entries):
    output = []
    for year in sorted({entry['year'] for entry in entries}, reverse=True):
        output.extend([f'<p class="pub-year">{year}</p>', '<ul class="pub-list">'])
        for entry in entries:
            if entry['year'] != year:
                continue
            link = ''
            if entry['url']:
                host = urlparse(entry['url']).hostname
                label = {'openreview.net': 'OpenReview', 'arxiv.org': 'arXiv',
                         'aclanthology.org': 'ACL Anthology'}.get(host, 'Paper')
                link = f' <a href="{url(entry["url"])}">[{label}]</a>'
            output.append(f'  <li>{entry["authors"]}. {entry["title"]}. {entry["venue"]}{link}.</li>')
        output.extend(['</ul>', ''])
    return '\n'.join(output).strip()


def news_html(entries, lang):
    output = []
    for entry in sorted((e for e in entries if e['news']),
                        key=lambda e: e['news']['date'], reverse=True):
        news = entry['news']
        if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', news['date']):
            raise ValueError('News date must be YYYY-MM')
        year, month = map(int, news['date'].split('-'))
        venue = entry['venue']
        venue = f'<strong>{venue}</strong>'
        title = entry['title']
        if entry['url']:
            title = f'<a href="{url(entry["url"])}">{title}</a>'
        first_author = entry['authors'].startswith('<strong>Kazuki Yano</strong>')
        if lang == 'en':
            date = f'{calendar.month_abbr[month]} {year}'
            kind = 'My first author paper' if first_author else 'Our paper'
            location = html.escape(news.get('location_en', ''))
            place = f' in {location}' if location else ''
            text = f'{kind} "{title}" accepted at {venue}{place}.'
        else:
            date = f'{year}年{month}月'
            kind = '主著' if first_author else '共著'
            location = html.escape(news.get('location_ja', ''))
            place = f'@{location}' if location else ''
            text = f'{venue} に{kind}が採択されました{place}'
        output.append(f'    <tr>\n      <td class="news-date">{date}</td>\n      <td>{text}</td>\n    </tr>')
    return '\n'.join(output)


def marked(text, name, content, initial_start=None, initial_end=None):
    start, end = f'<!-- BEGIN CV {name} -->', f'<!-- END CV {name} -->'
    block = f'{start}\n{content}\n{end}'
    if start in text and end in text:
        a, b = text.index(start), text.index(end) + len(end)
    elif start in text or end in text:
        raise ValueError('Incomplete generated section markers: ' + name)
    elif initial_start is not None:
        a = text.index(initial_start) + len(initial_start)
        b = text.index(initial_end, a) if initial_end else len(text)
        block = '\n\n' + block + '\n\n'
    else:
        raise ValueError('Missing generated section: ' + name)
    return (text[:a] + block + text[b:]).rstrip() + '\n'


def sync_pages(entries):
    updates = {}
    for relative, heading, end in [
        ('_pages/publications.html', '<h2>International Conference</h2>', None),
        ('_pages/ja/publications.html', '<h2>国際会議</h2>', '<hr>'),
    ]:
        path = ROOT / relative
        updates[path] = marked(path.read_text(), 'PUBLICATIONS', publication_html(entries), heading, end)
    for relative, lang in [('index.html', 'en'), ('_pages/news.html', 'en'),
                           ('_pages/ja/index.html', 'ja'), ('_pages/ja/news.html', 'ja')]:
        path = ROOT / relative
        text = path.read_text()
        if '<!-- BEGIN CV NEWS -->' not in text:
            anchor = '<table class="news-table">'
            text = text.replace(anchor, anchor + '\n<!-- BEGIN CV NEWS -->\n<!-- END CV NEWS -->', 1)
        updates[path] = marked(text, 'NEWS', news_html(entries, lang))
    return updates


def site_build():
    candidates = [shlex.split(os.environ['BUNDLE'])] if 'BUNDLE' in os.environ else [['bundle'], ['/usr/bin/bundle']]
    for command in candidates:
        try:
            check = subprocess.run(command + ['check'], cwd=ROOT, capture_output=True)
        except FileNotFoundError:
            continue
        if check.returncode == 0:
            run(command + ['exec', 'jekyll', 'build'])
            return
    raise RuntimeError('Jekyll dependencies missing. Set BUNDLE to the bundle executable used for this site.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_source = ROOT.parent / 'main.tex'
    parser.add_argument('--source', type=Path, default=default_source if default_source.exists() else ROOT / 'cv/main.tex')
    parser.add_argument('--push', action='store_true', help='Commit synchronized files and push the current branch')
    args = parser.parse_args()
    source = args.source.resolve()
    if args.push:
        if subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT).strip():
            raise RuntimeError('Commit or unstage existing staged changes before publishing.')
    text = source.read_text()
    entries = publications(text)
    updates = sync_pages(entries)  # Validate everything before writing.
    with tempfile.TemporaryDirectory(prefix='homepage-cv-') as temp:
        env = dict(os.environ, SOURCE_DATE_EPOCH=str(int(source.stat().st_mtime)), FORCE_SOURCE_DATE='1')
        for _ in range(2):
            run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                 '-no-shell-escape', f'-output-directory={temp}', f'-jobname={source.stem}',
                 # pdfTeX otherwise derives an ID from the random output path.
                 r'\pdftrailerid{}\input{' + source.name + '}'], cwd=source.parent, env=env)
        shutil.copyfile(Path(temp) / source.with_suffix('.pdf').name, source.with_suffix('.pdf'))
        shutil.copyfile(Path(temp) / source.with_suffix('.pdf').name, ROOT / 'files/CV.pdf')
    (ROOT / 'cv').mkdir(exist_ok=True)
    (ROOT / 'cv/main.tex').write_text(text)
    for path, content in updates.items():
        path.write_text(content)
    site_build()
    run(['git', 'diff', '--check'])
    if args.push:
        paths = [str(p.relative_to(ROOT)) for p in updates] + ['files/CV.pdf', 'cv/main.tex']
        run(['git', 'add', '--', *paths])
        if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode:
            run(['git', 'commit', '-m', 'Sync CV, publications, and news from main.tex'])
        run(['git', 'push'])
    print('Updated main.pdf, files/CV.pdf, publications, and annotated news.')


if __name__ == '__main__':
    main()

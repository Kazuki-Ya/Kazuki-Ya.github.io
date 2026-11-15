import unittest
import update_homepage as sync


class SyncTests(unittest.TestCase):
    def test_nested_tex_and_escaping(self):
        self.assertEqual(sync.tex_html(r'A \mbox{nested {phrase}} \& \textbf{B}'),
                         'A nested phrase &amp; <strong>B</strong>')
        with self.assertRaises(ValueError):
            sync.tex_html(r'\unknown{Do not silently publish broken TeX}')

    def test_real_cv_and_metadata(self):
        entries = sync.publications((sync.ROOT / 'cv/main.tex').read_text())
        self.assertEqual(len(entries), 10)
        self.assertEqual(entries[0]['news']['location_en'], 'Athens, Greece')
        self.assertTrue(all(e['news'] is None for e in entries[1:]))
        self.assertEqual(entries[-1]['url'], None)

    def test_repeated_sync_preserves_domestic_and_manual_news(self):
        entries = sync.publications((sync.ROOT / 'cv/main.tex').read_text())
        for path, content in sync.sync_pages(entries).items():
            original = path.read_text()
            if 'publications' in path.name:
                content2 = sync.marked(content, 'PUBLICATIONS', sync.publication_html(entries))
                if '/ja/' in str(path):
                    self.assertEqual(content.split('<hr>', 1)[1], original.split('<hr>', 1)[1])
            else:
                lang = 'ja' if '/ja/' in str(path) else 'en'
                content2 = sync.marked(content, 'NEWS', sync.news_html(entries, lang))
                self.assertIn('Carnegie Mellon University', content)
                self.assertNotIn('https://2027.eacl.org/', content)
            self.assertEqual(content2, content)

    def test_missing_year_and_unsafe_url_fail(self):
        with self.assertRaises(ValueError):
            sync.publications(r'\begin{document}\publication{T}{A}{EACL}{}')
        with self.assertRaises(ValueError):
            sync.publications(r'\begin{document}\publication{T}{A}{EACL 2027}{\href{javascript:bad}{Paper}}')


if __name__ == '__main__':
    unittest.main()

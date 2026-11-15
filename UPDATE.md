# CV とホームページの更新

普段は親フォルダの `main.tex` を編集してください。
親フォルダとこのリポジトリのどちらからでも実行できます。

```sh
make update   # PDF生成 → CV.pdf差し替え → 日英の論文・ニュース同期 → サイトビルド
make publish  # 上記を実行し、生成したファイルをcommitしてpush
```

必要環境は Python 3、pdfLaTeX、Git、およびこのサイトの Jekyll/Bundler 環境です。
Bundler は `bundle check` が成功する実行環境を選びます。明示する場合は
`BUNDLE=/usr/bin/bundle make update` のように指定してください。

## 論文

`main.tex` の `\publication{タイトル}{著者}{会議名と年}{リンク}` を編集します。
会議名には4桁の年を含め、リンクは `\href{https://...}{[Paper]}` または空欄にしてください。
日英の国際会議一覧を同じ情報から生成します。日本語ページの国内発表は手動編集のままです。
サイト上もCVと同じ会議名・リンクを使います。

対応するLaTeXは `\textbf`、`\textit`、`\emph`、`\mbox` と基本的な記号エスケープです。
未知の命令は誤ったHTMLを公開しないようエラーにします。

## 採択ニュース

ニュースを掲載したい論文の直前に、次のコメントを追加します。
日付は採択を告知する月です。開催地は公式情報を確認して記入してください。

```tex
% website-news: {"date": "2026-11", "location_en": "Athens, Greece", "location_ja": "アテネ🇬🇷"}
\publication{...}{...}{Findings of EACL 2027}{...}
```

`date` は必須、ほかは省略できます。主著・共著は先頭の著者から判定します。
日英のトップとニュース一覧を更新し、既存の手動ニュースは残します。
既存論文すべての採択ニュースを自動で追加することはありません。
HTMLの `BEGIN CV` ～ `END CV` 内は生成領域なので、元の `main.tex` を修正してください。
経歴や研究紹介などの自由文は従来どおりサイト側で編集します。

## ソース保存と公開

同期時に `cv/main.tex` にソースも保存し、PDF・論文・ニュースと一緒に履歴へ残します。
親の `main.tex` がない別のcheckoutでは、この保存済みソースを使用します。
別ソースを指定する場合は `python3 scripts/update_homepage.py --source /path/to/main.tex`。
`cv/` と `scripts/` はサイトの公開ファイルから除外しています。

`make publish` は生成対象だけをcommitし、現在のブランチを通常の `git push` で送信します。
先にステージされた変更がある場合は停止します。push失敗時はローカルcommitを残すので、
原因を解消して通常のGit操作で再送してください。

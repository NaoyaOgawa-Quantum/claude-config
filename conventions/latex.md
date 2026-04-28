# LaTeX 規約

LaTeX を含むリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/latex.md`

## 式の安全規則
- **equation/align 環境内は原則変更しない。** 変更は事前にユーザー確認。物理的内容の追加はコメントとして提案（ハルシネーション混入防止）
- 英語校正・文法修正など確実に正しい本文修正は可

## コンパイラ
- 英語のみ → `lualatex`
- 日本語含む → `ptex2pdf`（内部で platex + dvipdfmx）
- BibTeX フルビルド: `platex → bibtex → platex → platex → dvipdfmx`
- リポの CLAUDE.md に手順があればそちらを優先

## Bibliography スタイル
- **JHEP.bst を使う**（個人的好み）。`note` フィールドも表示するバージョンを使用
- 正本: `~/Claude/claude-config/JHEP.bst`（ver. 2.18 ベース + note 全 entry type で有効化、md5: `bcca8042…`）
- `setup.sh` が texmf-local にインストール（odakin: 自動、他ユーザー: オプション表示）
- texmf-local 未設定の場合は正本からリポにコピーして使う
- `\bibliographystyle{JHEP}` を指定

## JHEP.bst 記法
JHEP.bst はフィールドから自動リンクを生成するので `\href` 手書き不要（二重リンクの原因）。
- `doi`: DOI 本体のみ（例: `10.1103/PhysRevA.61.012104`）
- `eprint`: arXiv ID のみ（例: `quant-ph/9905023`）。`archivePrefix = "arXiv"` と併用
- `url`: doi や eprint があれば不要
- `note`: 自由テキスト。自動リンク対象外の補足情報に使う

## hyperref 設定
**新規 LaTeX ドキュメントは以下の hyperref 設定を使う:**
```latex
\usepackage[bookmarks=true,bookmarksnumbered=true,setpagesize=false]{hyperref}
```
- `\hypersetup{colorlinks=true}` は使わない。hyperref のデフォルト (`linkcolor=red`, `citecolor=green`, `urlcolor=magenta`) は赤緑紫がモトリーで見にくい。`allcolors=blue` で揃える手もあるが、印刷時にも色が乗るので避ける
- 上記 `[bookmarks=true,...]` 設定はリンク本文を黒のままにし、PDF annotation の薄い枠 (border box) のみ追加する。枠表示は viewer 依存（Preview/Adobe では薄く表示、印刷では非表示）
- 完全に枠も色も無くしたい場合は `\hypersetup{hidelinks}` を追加
- 既存の `\hypersetup{colorlinks=true}` がある場合はリンク色を改善するため上記に migrate する

## pre-commit hook（Unicode→LaTeX 自動修正）
`setup.sh` が LaTeX リポに自動インストール。手動確認・インストール:
```bash
# 確認: .git/hooks/pre-commit が fix-bib-unicode を指しているか
ls -la .git/hooks/pre-commit
# インストール:
ln -s ~/Claude/claude-config/scripts/pre-commit-bib .git/hooks/pre-commit
```
ステージされた `.tex`/`.bib` 等の非 LaTeX 文字（Unicode 引用符、ダッシュ等）を自動でLaTeXコマンドに変換する。

## ドキュメント読み取り

- **内容理解が目的なら PDF を `pages` パラメータ付きで読む。** tex ソースはトークン消費が大きい（数万トークンになることも）。PDF なら必要なページだけ効率的に読める
- tex は **数式の編集が必要な場合のみ** 開く。その場合も `offset`/`limit` で必要な範囲に限定する

## チャット本文での位置参照

- **ページ番号・セクション名・式番号で位置を示す。tex の行番号は使わない。** 行番号はツールが tex を読むときの内部座標で、ユーザー側 (PDF / TeXShop) には不可視。ユーザーがナビゲートできない参照は無効
- 行番号は Edit 等の tool 引数として内部で使うだけに留める
- ページ番号は `.aux` の `\newlabel{...}{{sec}{page}{...}}` から引ける。最新ビルドの aux が無ければ PDF を読んで確認する

## .gitignore
**LaTeX 生成 PDF はリポに含める（ignore しない）。** 共同編集者がコンパイル環境を持っていない場合でも最新の PDF を参照できるようにするため。`*.pdf` を ignore する場合は `!<main>.pdf` で除外対象から外す。

共有リポでは共同編集者のために .gitignore に LaTeX 中間ファイルのパターンを明記する（`~/.gitignore_global` に頼らない）:
```
*.aux *.bbl *.blg *.log *.out *.toc *.fdb_latexmk *.fls *.synctex.gz *.synctex(busy) *.dvi
```

## .gitattributes（改行コード正規化）

以下のケースでは LaTeX リポに `.gitattributes` を置くことを推奨:
- Dropbox / iCloud 等のクラウド同期配下で運用するリポ（同期中に改行コードが書き換わることがある）
- Windows 共同編集者がいる共有リポ（CRLF 混入で git が全行 diff と見なすのを防ぐ）

どちらにも該当しないリポ（Linux/Mac のみ、個人運用）では不要。

推奨内容:
```
# Normalize line endings to LF in the repository
* text=auto eol=lf

# Binary files — no conversion
*.pdf binary
*.png binary
*.jpg binary
```

# LaTeX 規約

LaTeX を含むリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/latex.md`

## 式の安全規則
- **equation/align 環境内は原則変更しない。** 変更は事前にユーザー確認。物理的内容の追加はコメントとして提案（ハルシネーション混入防止）
- 英語校正・文法修正など確実に正しい本文修正は可

## コンパイラ
- 英語のみ → `lualatex`
- 日本語含む → `ptex2pdf`（内部で platex + dvipdfmx）または `lualatex`（jlreq クラス等）
- BibTeX フルビルド:
  - platex 系: `platex → bibtex → platex → platex → dvipdfmx`
  - lualatex + 日本語著者: **`lualatex → upbibtex → lualatex → lualatex`**（後述「日本語著者の BibTeX 処理」 参照、`bibtex` は不可）
- リポの CLAUDE.md に手順があればそちらを優先

## Bibliography スタイル
- **JHEP.bst を使う**（個人的好み）。`note` フィールドも表示するバージョンを使用
- 正本: `~/Claude/claude-config/JHEP.bst`（ver. 2.18 ベース + note 全 entry type で有効化、md5: `bcca8042…`）
- `setup.sh` が texmf-local にインストール（odakin: 自動、他ユーザー: オプション表示）
- texmf-local 未設定の場合は正本からリポにコピーして使う
- `\bibliographystyle{JHEP}` を指定

## biblatex は使わない（JHEP.bst と非互換）

JHEP.bst は **legacy BibTeX 用の `.bst`** であり、`biblatex` とは互換性が無い。次のようなコードを見つけたら legacy BibTeX に切り替える:

```latex
% ❌ biblatex (JHEP.bst が効かない)
\usepackage[backend=bibtex]{biblatex}
\addbibresource{refs.bib}
...
\printbibliography

% ✅ legacy BibTeX (JHEP.bst 想定の正式記法)
\bibliographystyle{JHEP}
\bibliography{refs}
```

biblatex で同等の出力スタイルを使いたければ `biblatex-jheppub` 等の別パッケージが要るが、odakin の運用では legacy BibTeX + JHEP.bst が canonical。

## 日本語著者の BibTeX 処理

`bibtex`（legacy, ASCII 想定）は日本語著者を name parse できず、姓の最初の 1 文字が文字化け（U+FFFD）または "First Last" 誤判定で姓だけ消える。対策は 2 段:

**(1) コマンド**: `bibtex` でなく **`upbibtex`**（TeX Live 同梱、UTF-8 直接処理）を使う

```bash
# ❌ bibtex main          → 「川.~紳一」のような出力に化ける
# ✅ upbibtex main        → 日本語そのまま処理
```

**(2) refs.bib の表記**: 著者を `{...}` ブレースで囲み、bibtex の First/Last name parser を回避する

```bibtex
% ❌ bibtex は「川上」を First、「紳一」を Last と誤判定
author = {川上 紳一 and 吉田 英太郎}

% ✅ ブレースで姓名一括 → 単一 entity 扱い、化けない
author = {{川上 紳一} and {吉田 英太郎}}
```

JHEP.bst のような `F.~Last` 形式の bst では、ブレース内が全部 Last 扱いになって「川上 紳一」 のまま出力される。

## refs.bib 整備フロー（実物検証によるハルシネーション防止）

文献情報（著者・タイトル・巻号ページ）を refs.bib に追加する前に、次の優先順で**実物検証**する:

1. **PDF 実物が手元にある** → 直読して書誌情報を確定
2. **PDF 実物がない** → 同論文を引用している後発論文の参考文献欄で交差検証
3. **どちらも無い** → entry を作らない（推測で作らない）

**やってはいけないこと**:

- WebSearch の summary だけを根拠に entry を作る（summary は hallucinate する。`conventions/web-tools.md §「WebSearch の summary は hallucinate する」` 参照）
- 既存 refs.bib の entry を**検証せずに**信用する（共同編集者や過去の自分が誤同定している可能性。実例: 同名著者の別論文と取り違え、改訂版のタイトルを初版と混同 等）
- 似たキーワード・近い年代の論文を「これだろう」 と推測して埋める

**典型的な落とし穴**:

- Mandelbrot 1977 と 1982 で本のタイトルが違う（1977: *Fractals: Form, Chance, and Dimension* / 1982: *The Fractal Geometry of Nature*。同著者・近接年・関連内容で取り違いやすい）
- 同姓著者の別人（例: 「川上 紳一」 と「川上 智一」）
- 巻通しページと号内ページの混在（学会誌で 2 種の page number が併記される場合）

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

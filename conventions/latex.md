# LaTeX 規約

LaTeX を含むリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/latex.md`

## 式の安全規則
- **equation/align 環境内は原則変更しない。** 変更は事前にユーザー確認。物理的内容の追加はコメントとして提案（ハルシネーション混入防止）
- 英語校正・文法修正など確実に正しい本文修正は可

## 地の文に math 文字を裸で書かない (math mode 保護)

**ルール:** 地の文 (= `$...$` `\(...\)` `equation` 環境の外) では、 `^` `_` `\dagger` `\hat` 等の **math mode 専用記号を含む式片**を裸で書かない。 全部 `$...$` で囲うか、 日本語に置き換える。

**Why:** TeX は地の文で `^` `_` を見ると math mode 解釈を試み、 `Missing $ inserted` エラーで build が止まる (= 「Emergency stop」 まで行く)。 地の文に「a^†」 「α_n」 「c_{n+1}」 等を裸で書くのは典型的 bug 源。 章 draft 編集時に頻発、 編集者は気付きにくい (= rendered PDF を見ないと build 失敗が visible にならない)。

**How to apply (= edit 時 self-check):**
- 地の文に演算子記号 / 添字 / Greek + subscript を書く前に、 数式環境内かを確認
- 安全な置き換え:
  - `a^†` (地の文) → `$\hat{a}^\dagger$` または「a に dagger」 等の言い換え
  - `α_n` (地の文) → `$\alpha_n$` または「規格化定数」 等の言い換え
  - `|n+1⟩` (地の文) → `$\ket{n+1}$` または「次の段」 等の言い換え
- **edit 後 must build**: tex 編集後は必ず `make` / `ptex2pdf` で build を確認、 「Missing $ inserted」 エラーが出たら該当行を grep で見つけて修正
- 検出 grep (大まかに): `grep -nE '[^\$\\\\\{]a\^|[^\$\\\\\{]α_|[^\$\\\\\{]c_n' file.tex` 等

**事例 (2026-05-10 quantum-mechanics-textbook 第 1 部最終章 draft restructure)**: 7 commit に渡る章書き直しの過程で、 Claude が地の文に「a^† と a の代数構造」 「α_n の積」 「a^†|n⟩ ∝ |n+1⟩」 等を裸で書いて 3 箇所で build を破壊。 1 commit 内で 3 回 build retry が必要だった。 edit 直後の build verify で発覚 → 該当箇所を `$\hat{a}^\dagger$` 等で囲って修正。

## プリアンブル定義のマクロを優先する (絶対則)

**リポのプリアンブルで定義されているマクロ (semantic / typing shortcut / 色付き / 数式 alias / その他、種類問わず) が対象概念に存在する場合、生の primitive 記法を使うことを禁止する。**

⚠️ **「`\op` だけの話」 ではない**。プリアンブルで定義されているありとあらゆるマクロが対象。色付き semantic macro (`\op` `\st` `\rf` `\pd` 等) だけでなく、typing shortcut (`\h` = `\hat`、`\wh` = `\widehat`、`\tx` = `\text`、`\md` = `\middle|`、`\sqbr{}` = `\left[...\right]` 等) や数学演算子 (`\Tr`、`\fnl`、`\commutator{}{}` 等) も同等に強制対象。

例外は以下 **2 つに限定** (狭く解釈する):
1. プリアンブル定義が**無い**概念 (= grep で見つからない)
2. author drafting marker (= `\cl{}` `\green{}` 等の一時的 highlight、後で消す前提のスクラッチ、semantic 意味なし)

これ以外、「raw でも動くから raw で書く」 「見た目同じだから raw で OK」 「タイプが少し短いから raw で済ます」 は全部 NG。

### 対象範囲の例 (= 全部対象、これでも非網羅)

| カテゴリ | マクロ例 | 対応する生記法 (= 禁止) |
|---|---|---|
| 色付き semantic | `\op{T}` (operator + red) | `\red{T}`、`\hat{T}`、`\textcolor{red}{T}` |
| 色付き semantic | `\st\rho` (state + magenta + mathsfit) | `\magenta{\rho}`、`\hat\rho` 単体 |
| 色付き semantic | `\rf{f}` (real func + blue) | `\blue{f}` |
| 色付き semantic | `\pd{X}`、`\pdf{X}{x}` (prob dist + cyan) | `\cyan{X}`、`\cyan{X\fn{...}}` |
| 関数呼出 | `\fn{x}`、`\fnl{X}` (auto-spacing + paren/bracket) | `\paren{x}`、`(x)`、`\sqbr{X}` (function call 文脈で) |
| 数学演算子 | `\Tr`、`\Tr\fnl{X}` | `\tx{Tr}`、`\Tr\sqbr{X}`、`\Tr[X]` |
| 数学演算子 | `\commutator{A}{B}` | `[A,B]` (commutator 文脈で) |
| typing shortcut | `\h` (= `\hat`) / `\wh` (= `\widehat`) | `\hat{}` / `\widehat{}` |
| typing shortcut | `\tx` (= `\text`) / `\mc` (= `\mathcal`) / `\ms` (= `\mathscr`) | `\text{}` / `\mathcal{}` / `\mathscr{}` |
| typing shortcut | `\md` (= `\middle|`) | `\middle\|` |
| 物理 alias | `\rh` (= `\hat\rho`)、`\Ah` (= `\hat A`)、`\TD` (= `T_\tx{D}`) 等 | バラ書き (`\hat\rho`、`\hat A`、`T_\tx{D}`) |

### 確認用 grep (= 「定義がある macro 名なのか?」 をチェック)

```bash
# ある token (e.g. \red, \op, \fn, \Tr) の定義をプリアンブルで探す
grep -nE '\\(newcommand|renewcommand|providecommand|nc|def|NewDocumentCommand|DeclareDocumentCommand|DeclareMathOperator)\*?\{?\\<token>' main.tex
```

`\NewDocumentCommand` / `\nc` (= `\newcommand` の独自 shortcut) / `\providecommand` 形式は `\newcommand` 1 種類だけ grep してると見落とすので、上の widening grep を必ず使う。

### 理由 (rule の hard 化を支える 4 条)

1. **一斉追従**: macro 定義を refine (e.g. journal 投稿時に色除去 + ハットスタイル変更、フォント差し替え) すると全箇所が一斉追従、生記法は drift する。プリアンブルがあるのに使わないと「定義したが効かない」 dead 領域になる
2. **Greppability**: `\op{T}` は概念として grep 可能 (= 全 operator 占用箇所が `grep '\\op{'` で引ける)、生 `\hat{T}` は raw notation で grep しても operator かどうか判別不能
3. **意図の明示**: `\op{T}` は読み手に「operator T」 を伝えるが、`\hat{T}` は単なる hat 記号で物理 / 数学的意味が伝わらない
4. **共著者・後継者の dx**: 1 人が手で raw を選ぶたびに、共著者の grep が外れる、後継者の refine が壊れる、レビュアーが「なぜここだけ違うの?」 と問う。**プリアンブル定義 = 既に「これを使え」 と全員に向けて宣言されている。raw 書きはその宣言を裏切る行為。**

### リポ固有 fallback

リポ固有の active semantic macro 一覧と例外運用は各リポの `CLAUDE.md §LaTeX rules` 参照 (Layer 2)。Layer 1 の本則は「プリアンブルにあれば必ず使う」、Layer 2 は「このリポで何が active か」 のディレクトリ。

## コンパイラ

odakin の標準は **pdf 直接出力 (= pdftex 系)**。tex+dvi+dvipdfmx の 2 段ワークフローは**英語論文では使わない**。

- **英語のみ** → **`lualatex`** が odakin の標準 (= TeXShop が `LuaTeX-1.21.0` で生成、PDF Producer 欄で確認済)。`pdflatex` も可 (どちらも pdf 直接出力で互換)
- **日本語含む** → `ptex2pdf` (内部で platex + dvipdfmx) または `lualatex` (jlreq クラス等)
- **BibTeX フルビルド**:
  - **lualatex (英語、odakin 標準)**: `lualatex → bibtex → lualatex → lualatex`
  - pdflatex (英語、互換代替): `pdflatex → bibtex → pdflatex → pdflatex`
  - lualatex + 日本語著者: **`lualatex → upbibtex → lualatex → lualatex`**（後述「日本語著者の BibTeX 処理」 参照、`bibtex` は不可）
  - platex 系 (日本語、tex+dvi 経由): `platex → bibtex → platex → platex → dvipdfmx`
- リポの CLAUDE.md / README に手順があればそちらを優先

⚠️ **graphics 駆動 driver の罠**: `\usepackage{graphicx}` の default driver は engine 依存:
- pdflatex / lualatex → pdftex / luatex driver (= .pdf を直接読める、.xbb 不要)
- platex (tex+dvi) → dvips driver (= .pdf 不可、.xbb もデフォルトでは読まない)

英語論文を pdflatex で書いていれば graphics は素直に動く。platex 系で .pdf 図を使うなら `\usepackage[dvipdfmx]{graphicx}` または `\documentclass[...,dvipdfmx]{...}` が必要。

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
`setup.sh` が **全リポに自動インストール** (Step 6)。 hook 自体が staged file 中の `.tex/.bib/.bst/.cls/.sty` の有無を判定し、 LaTeX file 不在の repo では no-op で exit 0 (`scripts/pre-commit-bib` L31-35)。 よって LaTeX file 検出は install 時に不要、 全 repo install で robust。

手動確認・インストール:
```bash
# 確認: .git/hooks/pre-commit が pre-commit-bib を指しているか
ls -la .git/hooks/pre-commit
# インストール (setup.sh が走らなかった repo の retroactive fix):
ln -s ~/Claude/claude-config/scripts/pre-commit-bib .git/hooks/pre-commit
```

ステージされた `.tex`/`.bib` 等の非 LaTeX 文字（Unicode 引用符、ダッシュ等）を自動でLaTeXコマンドに変換する。 具体例:

- `—` (Unicode em-dash U+2014) → `---` (LaTeX em-dash command)
- `–` (Unicode en-dash U+2013) → `--`
- `"..."` (Unicode smart quotes) → `` ``...'' ``
- `ö` 等 Unicode 西欧文字 → `{\"o}` 等の LaTeX accent command

**Claude への規律**: `.tex/.bib` を新規作成・編集する前に本 convention を読むこと。 Markdown 流儀で literal `—` を直書きすると LaTeX で正しく render されない (Unicode em-dash は通常の LaTeX font に欠落することが多い)。 hook が機械的に catch するが、 hook 未 install repo では catch されない (= 2026-05-14 個人層 private repo の深い path で発生、 RCA は `claude-config/DESIGN.md`)。

### 旧設計の失敗 (2026-05-14)

旧 setup.sh Step 6 は「`.tex/.bib` を含む repo にだけ install」 という時点依存検出を採用していた。 問題は 2 つ:

1. **時点依存**: setup.sh 実行時に `.tex` 不在の repo は skip → 後から `.tex` 追加されても hook 未 install のまま
2. **bash glob 深度不足**: 検出 logic `ls "$REPO_DIR"**/*.tex` は globstar 無効時に 1 階層しか見ない。 個人層 private repo の `.tex` が深い path (depth 4) で detection failed

→ 全 repo install に切替えた (hook 自体が no-op skip するので害無し)。 移行は `setup.sh` を 1 回再実行すれば既存 repo に retroactive install される。

### fix-bib-unicode の codepoint scope (2026-05-15 確認)

hook (`scripts/fix-bib-unicode.py`) の `UNICODE_MAP` は **U+2013 (en-dash) と U+2014 (em-dash) のみ** dash 系で handle する。 他の「視覚的に似ているが codepoint が違う horizontal-line 系文字」 は scope 外:

| codepoint | 字形 | hook 挙動 | 物理書での出処 |
|---|---|---|---|
| U+2013 | `–` (en-dash) | → `--` | 範囲記号 (page 12--15) |
| U+2014 | `—` (em-dash) | → `---` | 欧文 em-dash |
| **U+2500** | `─` (box drawings light horizontal) | **scope 外、 保持** | 日本語典籍の罫線 (1 つでは細い、 2 つ並べて `──` で長い横棒) |
| U+2015 | `―` (horizontal bar) | scope 外、 保持 | 日本語小説の dash 様 (= em-dash 様の太い横棒) |
| U+30FC | `ー` (katakana-hiragana prolonged sound mark) | scope 外、 保持 | カタカナ長音 (= dash ではないが視覚的に紛らわしい) |

**Claude 規律**: `.tex/.bib` を書くとき、 「視覚的に em-dash」 のつもりで何の codepoint を打鍵しているか自覚する。 input method (= IME) が打鍵によって違う codepoint を吐くことがあり、 同じ文書内で codepoint 不一致が発生する (= 2026-05-15 個人層 private 日本語 LaTeX project の lecture draft で comments 部 U+2014 / body 部 U+2500 の混在を 1 セッション内で気付かずに作成、 hook が U+2014 のみ変換した結果 visual 一致だが source 不一致に着地)。 IME の確認 + 章執筆 1 個分書いたら `grep -P "[\x{2013}\x{2014}\x{2015}\x{2500}]"` で出現 codepoint を audit する。

## 日本語横罫線 (em-dash 系) の書き方 (2026-05-15、 個人層 LaTeX project 経験で導入)

日本語典籍 (= 物理書・数学書・小説・新聞) で多用される「**思考の挿入・補足・話題転換**」 を示す長い横棒 (typographically: `──` or `――`) を LaTeX で書く 3 方式の比較。 視覚的には全て似ているが source / build / hook との相互作用が異なる。

| 方式 | source 例 | PDF 出力 (uplatex + jsbook/jsarticle) | hook 相互作用 | 視覚的 feel |
|---|---|---|---|---|
| (a) U+2500 doubled | `本章はこう書く ── これが結論` | 日本語 font の box drawings light horizontal glyph × 2 = `──` (細く均一の幅の罫線 2 連) | hook scope 外、 保持 | 日本語典籍に最も忠実 |
| (b) LaTeX em-dash | `本章はこう書く --- これが結論` | em-dash 1 個 = `—` (タイポグラフィ的な横棒 1 本) | hook が U+2014 → `---` に変換 (= source clean を保てる) | 欧文 em-dash スタイル、 やや短い |
| (c) LaTeX em-dash doubled | `本章はこう書く ------ これが結論` | em-dash 2 個隣接 = `——` (タイポグラフィ的な横棒 2 連) | ASCII only、 hook 介入なし | (a) に近い罫線風、 ただし接続点に細い seam が見えうる |

**ligature 機構**: LaTeX で `---` は 3 文字 ligature として em-dash 1 個に変換される。 `------` は 「`---` + `---`」 と parse され em-dash 2 個になる。 `----` (4 文字) は `---` + `-` で em-dash + hyphen、 `-----` (5 文字) は `---` + `--` で em-dash + en-dash になるので、 横罫線目的なら 3 の倍数 (= 3 か 6) を使う。

**推奨選択** (= 2026-05-15 個人層 LaTeX project の lecture draft 判断):

- **日本語典籍に近い見た目**を最優先 → (a) U+2500 doubled。 ただし IME 由来の codepoint 混在事故に注意 (= 上の「fix-bib-unicode の codepoint scope」 参照)
- **source ASCII clean + hook 非依存**を優先 → (c) `------`。 (a) に近い視覚 feel を ASCII で実現
- **欧文流儀でよい / 単一の em-dash で十分** → (b) `---`。 最もシンプル

**過去の事故 + 判断経緯**: 個人層 LaTeX project の lecture draft で当初 (a) U+2500 doubled を使用、 5/15 セッションで Claude が「uplatex + okumacro が日本語横罫線として render する」 と verify なし主張、 user の「これ本当?」 で実物 verify、 (b) `---` に一旦切替するも user が日本語典籍の見た目を考慮し直して (c) `------` に再切替で着地。 okumacro は実際には U+2500 の render に関与しておらず、 単に uplatex default の日本語 font が U+2500 を box-drawing glyph で render するだけだった (= Claude の typographic 主張は実物 verify なしには信用しない、 詳細規律は個人層 work-discipline.md §「Typographic claim」)。

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

---

## 日本語長 title の文節境界改行 (title_wrap pattern)

ポスター・slide・cover page 等の **display title** で日本語 long title (= 15 文字以上) を扱う時、 LaTeX の auto-wrap は機械的に「N 文字/行」 で改行するため、 助詞「に」 「の」 や単語「保存量」 の途中で改行されて editorial 不自然になる。

**例**: 「一般相対性理論における二つの保存量:エネルギーと重力電荷」 (17 chars)

- auto-wrap (= 32pt × text_width 100mm): 「一般相対性理論に / おける二つの保存 / 量:エネルギーと重 / 力電荷」 (= 4 行、 助詞・単語途中改行)
- title_wrap で手動指定: 「一般相対性理論における / 二つの保存量: / エネルギーと重力電荷」 (= 3 行、 文節境界)

### How to apply

1. yaml の data file に `title_wrap.ja` 配列 (= 行 list) を optional field で許可:
   ```yaml
   title:
     ja: "一般相対性理論における二つの保存量:エネルギーと重力電荷"   # 純粋なタイトル (= web 用、 wrap なし)
   title_wrap:
     ja:
       - "一般相対性理論における"
       - "二つの保存量:"
       - "エネルギーと重力電荷"
   ```
2. build script で `title_wrap.ja` を LaTeX の改行 (`\\`) で結合して inject:
   ```python
   title_for_template = " \\\\ ".join(line.strip() for line in title_wrap)
   ```
3. font size は **最大行の文字数が text_width 内に収まる** ように choose:
   - default 40pt: 約 7 chars/line (= 100mm width)
   - 32pt: 約 9 chars/line
   - 25pt: 約 11 chars/line

### When to use

short title (= 13 chars 以下) は auto-wrap で OK、 title_wrap 不要。 long title で auto-wrap 結果が editorial 不自然なときのみ **opt-in** で使う (= 全 title に title_wrap を強制すると過剰運用、 short title での手動指定は冗長)。

### font override pattern (= long content への対応)

title だけでなく abstract 等の長 content も同様の課題が出る (= 2 段落 abstract が default 10pt で footer 領域を侵食、 等)。 解: yaml に `font.{title,abstract}.{size,leading}` override block を許可、 default は template の `\providecommand` で:

```yaml
font:
  title:
    size: 25         # default 40 (pt)
    leading: 31      # default 46 (pt)
  abstract:
    size: 9.5        # default 10 (pt)
    leading: 14.5    # default 17 (pt)
```

template 側:
```latex
\providecommand{\seminartitlefontsize}{40}
\providecommand{\seminartitleleading}{46}
% ...
{\fontsize{\seminartitlefontsize pt}{\seminartitleleading pt}\selectfont \seminartitleja}
```

これで content 長に応じた個別 case adjustment を yaml で完結 (= テンプレ本体は触らない、 各 case は yaml の override で対応)。

### paragraph break の保持 (= 段落区切り)

abstract 等の長 content で **段落区切り**を保ちたい場合: yaml の block scalar `|` の空行は LaTeX `\providecommand{...}{<value>}` 内では消える (= 単純 space 化される) ので、 build script で `\n\n` → `\par ` 変換する:

```python
abstract_latex = re.sub(r"\n\s*\n", r"\\par ", abstract_yaml)
```

PDF 上で段落区切りが visible (= LaTeX default `\parskip` で 1 行分の vertical gap)。 強調したいなら template 側で `\setlength{\parskip}{4pt}` 等。

### Why

editorial typography で「機械改行を許容しない」 のは標準。 magazine cover / book cover / 学会ポスター等の display title は **文節境界改行**が defacto standard で、 auto-wrap 結果は visual quality を下げる。 yaml で行配列を持つ pattern は (a) wrap が text 編集の一部として扱える (b) display と web (= wrap なし) で同じ source から両方 generate できる、 2 つの利点がある。

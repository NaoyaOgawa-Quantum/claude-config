# Office automation (macOS): xlsx form fill, PDF conversion, TTS review

研究費応募書類 / 教務書類 / 学術様式の Excel xlsx を **openpyxl で fill する作業**、 および生成物の **PDF 化 / 印刷 / 音声読み上げ** に関する規約と落とし穴集。

origin: 2026-05 SPReAD (AI for Science 萌芽的挑戦研究創出事業) 応募で得た知見 (= 様式 1 研究計画調書 xlsx の Python 自動 fill、 figure 埋め込み、 字数制限管理、 PDF snapshot 生成、 TTS 確認)。

---

## 0. 開始前に form を **必ず dump する** (= 推測で書かない)

雛形 xlsx を受け取ったら、 fill コードを書く前に必ず構造を全部出力する。 form ごとに layout・merged 範囲・data validation・列幅・font が異なる。 推測で write 先 cell を決めると merged の途中・validation 不整合・列幅と合わない font size を踏む。

下記 `dump_form.py` を雛形毎に 1 回実行 → 出力を見て fill 対象 cell を確定する:

```python
#!/usr/bin/env python3
"""Inspect xlsx template structure: cells, merged, validation, column widths."""
import sys
from openpyxl import load_workbook

PATH = sys.argv[1] if len(sys.argv) > 1 else 'template.xlsx'
wb = load_workbook(PATH, data_only=False)

for sname in wb.sheetnames:
    ws = wb[sname]
    print(f"\n========== Sheet: {sname} ({ws.max_row}r × {ws.max_column}c) ==========")
    # Column widths
    print("\n-- Column widths --")
    for col_letter in 'ABCDEFGHIJKLMN':
        cd = ws.column_dimensions.get(col_letter)
        if cd and cd.width:
            print(f"  {col_letter}: {cd.width:.1f}")
    # Merged ranges
    if ws.merged_cells.ranges:
        print("\n-- Merged ranges --")
        for r in ws.merged_cells.ranges:
            print(f"  {r}")
    # Data validations (standard format; extension format is NOT readable by openpyxl)
    if ws.data_validations.dataValidation:
        print("\n-- Data validations --")
        for dv in ws.data_validations.dataValidation:
            print(f"  sqref={dv.sqref}, type={dv.type}, formula1={dv.formula1}, operator={dv.operator}")
    # All non-empty cells (label or value)
    print("\n-- Non-empty cells --")
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None:
                v = str(c.value).replace('\n', '⏎')[:80]
                print(f"  {c.coordinate} (font={c.font.size}pt {c.font.name or '?'}, wrap={c.alignment.wrap_text}): {v}")
```

実行: `python3 dump_form.py /path/to/様式1.xlsx | tee form-structure.txt`

出力を `form-structure.txt` に保存しておくと、 fill code 書きながら同時に参照できる + 後で再 fill する時 (= 雛形更新時) の diff も取れる。

> **注**: openpyxl は **extension 形式の data validation** (Excel 2007+ で追加された list dropdown 等) を読めない (= `UserWarning: Data Validation extension is not supported and will be removed` で警告 + skip)。 dropdown 選択肢を知るには 雛形 xlsx を Excel/Numbers で開いて目視するか、 「リスト」 タブ (= form 内部の選択肢シート) を openpyxl で別途読む。

## 0.5. ファイル命名規約 (form 別 registry)

行政・学術 form ごとに「ファイル名フォーマット」 が指定されている場合が多い。 fill 先のファイル名は **form 仕様通り** に作る (= submit 時の自動検証に必要)。 観測したパターン (placeholder のみ、 literal は private repo 側に置く):

| Form | 命名規則 |
|---|---|
| JST SPReAD 様式1 | `様式1＿研究計画調書＿<機関コード半角数字>＿<姓ローマ字><名ローマ字>.xlsx` (区切りは **全角アンダースコア `＿`**、 「様式1」 の `1` は半角、 ローマ字氏名は姓名の順で連続書き) |
| 科研費 学振 DC1/DC2 | (個別の e-Rad 仕様、 form 毎に DC1.pdf / DC2.pdf 形式が指示される) |
| 学内・財団推薦書 (汎用) | `<書類種別>_<年度>_<対象者識別>_<目的>.<拡張子>` (区切りは form 仕様に従う、 半角_全角＿混在に注意) |

**最重要 gotcha — 区切り文字の半角/全角**: 公的様式の多くは雛形ファイル名で `＿` (全角アンダースコア、 U+FF3F) を使う。 user が補完入力する際に `_` (半角、 U+005F) で書くと spec 違反になる場合がある。 雛形ファイル名そのままを copy して提出側パーツだけ追記する方が安全。 「様式1」 の数字部分は 雛形によって半角/全角バラバラ (雛形 instruction では「様式１」 = 全角だが、 配布 file 名は「様式1」 = 半角、 など)。 **雛形 file 名を grep して、 文字種を厳密に確認する** のが第一歩。

新 form を扱う時は雛形の「記入にあたっての留意事項」 タブを最初に grep して、 ファイル名仕様を抽出する。 規則違反は submit 時に reject されることがあるため厳守。

---

## 1. openpyxl xlsx fill の落とし穴

### 1-1. `XLImage.width` / `.height` setter は silent fail する

**症状**: `openpyxl.drawing.image.Image` (= `XLImage`) のインスタンスに `img.width = 600` / `img.height = 400` を代入しても save 後の xlsx には反映されず、 元 PNG のオリジナル解像度がそのまま埋め込まれる。 Excel 側では rendered display で縮小されているように見えるので気づきにくい。

**原因**: `XLImage.width` / `.height` は内部の `PIL.Image` インスタンスの `width` / `height` プロパティを proxy しているが、 PIL 側は **read-only**。代入は silent に no-op になる。

**正しい解法**: PIL で実 resize して別ファイルに保存、 それを embed する。

```python
from PIL import Image as PILImage
from openpyxl.drawing.image import Image as XLImage

src = Path('research-flow.png')
resized = Path('research-flow-embed.png')
target_width_px = 640

pil = PILImage.open(src)
new_size = (target_width_px, int(target_width_px * pil.height / pil.width))
pil.resize(new_size, PILImage.LANCZOS).save(resized)

img = XLImage(str(resized))  # ← resized 版を embed
ws.add_image(img)
```

### 1-1b. 画像挿入は `wb[シート名]` で参照、 `wb.sheetnames[N]` の数値 index は罠

**症状**: 「5 枚目のシート」 という指示を `wb.sheetnames[4]` で取ると、 form template が先頭に参考シート (= 「はじめにご確認ください」 / 「府省共通経費取扱区分表」 等) を持っている場合、 実際は「研究計画調書\_3 枚目」 を指してしまう。 結果として SS が間違ったシートに貼られる。

**正しい解法**: シート名を**直接指定**する。

```python
wb = load_workbook(xlsx_path)
# Bad: ws = wb[wb.sheetnames[4]]   # 5 枚目目的だが index で取ると参考シートを跨ぐと壊れる
# Good:
ws = wb['研究計画調書_5枚目']        # form template の実際のシート名で参照
img = XLImage(ss_path)
img.anchor = 'A1'
ws.add_image(img)
```

事前に `print(wb.sheetnames)` で全シート名を dump して目的のシートを目視で特定する習慣を持つ (= §4-1 「最初に dump」 原則と同源)。

### 1-2. 画像 anchor は `OneCellAnchor` + `ext` で完全制御

**症状**: `img.anchor = 'A13'` (string) は openpyxl 内部で `OneCellAnchor` に変換されるが、 ext (= 表示サイズ) は画像 metadata に依存して不安定。 また cell の top-left ぴったりに anchor すると上の cell の罫線と接触して**罫線を切る**ように見える。

**正しい解法**:

```python
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D

EMU_PER_PX = 9525  # 96 DPI で 1 px = 9525 EMU
OFFSET_PX = 10      # cell の top-left からのオフセット (= 罫線との空き)

img.anchor = OneCellAnchor(
    _from=AnchorMarker(
        col=0, row=12,            # 0-indexed: col 0 = A、row 12 = 1-indexed の 13 行目
        colOff=EMU_PER_PX * OFFSET_PX,
        rowOff=EMU_PER_PX * OFFSET_PX,
    ),
    ext=XDRPositiveSize2D(
        cx=EMU_PER_PX * resized_width_px,
        cy=EMU_PER_PX * resized_height_px,
    ),
)
ws.add_image(img)
```

- `_from.row` / `.col` は **0-indexed** (= openpyxl の cell address 1-indexed と混乱しがち)
- 罫線切り回避には `colOff` / `rowOff` で数 px 内側に配置
- 行高は画像の pt 換算 (`px × 72 / 96`) + offset + padding で確保

### 1-3. 列幅の単位は Excel "0-glyph" units (= 不直感)

**問題**: `ws.column_dimensions['A'].width` の値 (例: 96.64) は px でも pt でもない。「default フォントで "0" 文字を何個並べられるか」 という独自単位。 Japanese 全角文字の幅推定には換算が必要。

**換算式**:

```python
# col_width = ws.column_dimensions['A'].width  # 例: 96.64
pixel_width = col_width * 7.0                  # Excel column width × 7 px ≈ 実 px 幅
char_px_japanese = font_size * 1.33            # 全角 char 幅 ≈ font_size pt × 1.33
chars_per_line = int(pixel_width / char_px_japanese * safety)  # safety=0.92~0.95
```

96.64 units、 10pt MS Pゴシック → 676 px ÷ 13.3 px/char × 0.92 ≈ **46 chars/line** (全角)。

### 1-4. `wrap_text=True` だけでは Excel は行高 auto-fit しない

**症状**: cell に `Alignment(wrap_text=True)` を set + 長文書き込みしても、 openpyxl で save した xlsx を Excel で開くと行高が小さいまま (= text が切れて 1 行だけ表示)。

**原因**: Excel の auto-fit row height は user 操作 (ホーム → 書式 → 行の高さの自動調整) で発動する機能で、 ファイル open 時に自動実行されない (= openpyxl 経由の save は customHeight=True で固定扱い)。

**正しい解法**: 行高を openpyxl 側で **論理的に計算して explicit set** する。

```python
from openpyxl.styles import Alignment

def fit_cell(ws, addr, content, line_height_pt=12.5, pad_pt=4, safety=0.95):
    """wrap_text を有効化し、 column width から chars/line を auto 算出して行高を set。"""
    cell = ws[addr]
    cell.alignment = Alignment(wrap_text=True, vertical='top',
                                horizontal=cell.alignment.horizontal or 'left')
    if content is None:
        return
    col_letter = cell.column_letter
    col_width = ws.column_dimensions.get(col_letter)
    col_width = (col_width.width if col_width and col_width.width else None) \
        or ws.sheet_format.defaultColWidth or 8.43
    font_size = cell.font.size or 10
    chars_per_line = max(1, int(col_width * 7.0 / (font_size * 1.33) * safety))
    text_lines = str(content).split('\n')
    wrap_lines = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line)
                     for line in text_lines)
    height = max(20, wrap_lines * line_height_pt + pad_pt)
    ws.row_dimensions[cell.row].height = height
```

経験値:
- `line_height_pt = 12.5` (10 pt フォント × 1.25 line spacing 相当)
- `pad_pt = 4` (= 上下 margin 計 4 pt)
- `safety = 0.95` (= chars/line を保守的に縮めて wrap 安全)

これより generous (line_height=14、 pad=14) にすると cell 下に **余白が貯まる** (user 視覚で「スカスカ」 感)、 tight すぎる (line_height=11、 pad=0) と最終行が clip する。

### 1-5. Excel data validation の auto-resize は外部信号で発動しない

`ws.data_validations.dataValidation` で読める validation rule (例: `type=whole, formula1=9999999`) は openpyxl で write しても Excel 側の dropdown / 入力制限が発動するかは Excel version 依存。 リスト dropdown (extension 形式) は openpyxl が読めず警告を出す。 **値の正当性は openpyxl 側で別途検証する**。

### 1-6. xlsx は Excel に open されている間は openpyxl から save できない

**症状**: `wb.save(path)` が `PermissionError: [Errno 13]` で fail する、 または silently 別 tempfile に書いて消える。

**原因**: Excel が xlsx を編集モードで lock している。

**正しい解法**: 再 fill する前に必ず Excel を quit:

```bash
osascript -e 'tell application "Microsoft Excel" to quit' 2>/dev/null
sleep 1
python3 fill_xlsx.py
open -a "Microsoft Excel" /path/to/output.xlsx
```

`fill_xlsx.py` を反復実行する work-loop ではこの 3 行を冒頭に置く。

### 1-7. Merged cells への write は top-left のみ有効

**症状**: 例えば `B7:I7` が merged なのに `ws['D7'] = 'value'` と書いても表示されない (= D7 は merged の途中で、 top-left は B7)。

**正しい解法**: dump で merged 範囲を確認、 必ず **左上 cell** に write:

```python
# B7:I7 merged → 必ず B7 (= top-left) に書く、 D7 や F7 ではない
ws['B7'] = 'my-input-value'
```

`ws.merged_cells.ranges` で全 merged 範囲を列挙できる (上記 §0 `dump_form.py` 参照)。

### 1-8. Boolean checkbox cell は narrow column で `###` 表示

**症状**: `ws['F20'] = True` と書いた cell が Excel で `###` と表示される。 値そのものは TRUE で正しい。

**原因**: Excel は bool を `TRUE` / `FALSE` の文字列幅で render する。 列幅が narrow (= 4 chars 程度未満) だと `###` overflow indicator になる。 多くの form template は label と組み合わせる narrow column 想定で bool を置くので、 `###` が正常表示。

**対処**:
- 機能上は問題なし (値は TRUE)、 表示だけ気にしない
- どうしても見えるようにしたいなら、 該当列を一時的に広げる: `ws.column_dimensions['F'].width = 6`
- ただし form 雛形の列幅変更は他の cell 表示を崩すリスクがあるため、 表示優先より値優先を取る

### 1-9. 値の型 (`int` vs `str`) は form の仕様で決まる

**判定基準** (form の cell 仕様から):

1. **`=LEN(<cell>)` のような counter formula が当該 cell に紐付いている** → str で write (LEN は string 長を期待、 int 渡しても内部 stringify されるが想定外動作のリスク)
2. **`data validation type=whole` (= 整数要求) が当該 cell に付いている** → int で write (= 検証 pass)
3. **両方ある** → form 設計矛盾。 data validation 優先 (= int)、 counter は通らないが多くの form でエラー扱いされない
4. **どちらもない** → 数値は int、 文字列は str、 default 通り

`ws.data_validations.dataValidation` で type を、 隣接 cell の formula で counter を、 §0 dump で同時に確認する。

```python
# 例: 研究者番号 cell が type=whole validation 付き、 counter なし → int
ws['B6'] = 12345678          # int で write

# 例: 課題名 cell が =LEN(B22) counter 付き → str (本来 string なので素直)
ws['B22'] = '研究課題名のテキスト'

# 例: 生年月日 cell が yyyymmdd 半角数字指定 + type=whole → int
ws['B10'] = 19990101          # int (= 8 桁 yyyymmdd)
```

### 1-10. Print area / page setup を設定して PDF を 1 ページ化

xlsx → PDF 変換 (§2-1) で 1 sheet が複数ページに分割される問題は、 form 雛形が print area を設定していないことが原因。 openpyxl で fit-to-width を強制:

```python
from openpyxl.worksheet.page import PrintOptions, PageMargins

ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 0  # = unlimited (縦は何ページでも可、 幅だけ 1 ページ)
ws.sheet_properties.pageSetUpPr.fitToPage = True
ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.5, bottom=0.5)
ws.print_options.horizontalCentered = True
```

研究費 form の場合: 実提出は xlsx そのものなので print area 設定は省略可。 確認用 PDF を綺麗に出したい時のみ追加。

---

## 2. xlsx / md → PDF 変換 (macOS)

### 2-1. xlsx → PDF: Excel AppleScript

```bash
osascript << OSAEOF
tell application "Microsoft Excel"
    activate
    if (count of workbooks) = 0 or (name of workbook 1 does not contain "MyForm") then
        open POSIX file "/path/to/MyForm.xlsx"
        delay 2
    end if
    save active workbook in "/path/to/MyForm.pdf" as PDF file format
end tell
OSAEOF
```

注意:
- Excel が起動していて active workbook がないと「Not open」 エラーになるので、`if (count of workbooks) = 0` で防御
- `save as PDF file format` は Excel for Mac の `ExportAsFixedFormat` 相当、 全 sheet を印刷範囲設定に従って出力
- 印刷範囲・ページレイアウトが未設定の場合、 各 sheet が複数ページに分割される。 提案書用途では問題ないが、 単一ページに収めたい場合は事前に `ws.page_setup.fitToWidth = 1` などを openpyxl で set

### 2-2. md → PDF: Chrome headless + Python markdown

```python
import markdown, subprocess
from pathlib import Path

html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'toc'])
html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 18mm; }}
body {{ font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif;
        line-height: 1.55; font-size: 10.5pt; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #888; padding: 4px 8px; }}
</style></head><body>{html_body}</body></html>"""

Path('/tmp/out.html').write_text(html, encoding='utf-8')
subprocess.run([
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
    '--print-to-pdf=/path/to/out.pdf',
    'file:///tmp/out.html',
], check=True)
```

注意:
- Chrome `--headless=new` を必ず使う (旧 `--headless` は 2024 以降 deprecated)
- `--no-pdf-header-footer` で URL / ページ番号の footer を抑制
- 日本語 font は `font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif` で macOS native font を指定 (= TeX 経由より高速 + 字体が綺麗)
- pandoc は不要 (= 別途 install せずに済む)、 Python `markdown` ライブラリで HTML 生成 + Chrome で render

### 2-3. PDF は確認 / 印刷 / 後参照用、 提出は xlsx 本体

研究費応募 (e-Rad) や事務書類提出時、 PDF は **reference snapshot** で、 実提出は xlsx (or docx) 本体。 PDF と xlsx が drift しないよう、 PDF は `fill_xlsx.py` 実行後に再生成する pipeline にする。

### 2-4. docx → PDF: Pages.app AppleScript が macOS では最も robust

**選択肢**:
1. **Pages.app** (macOS 標準、 install 済): 一番安定。 ⭐ 推奨
2. **Microsoft Word** AppleScript: 動くが変数 scope 罠あり (`set theDoc to open ...` の戻り値が「変数定義されていない」 エラーになる)
3. **LibreOffice** `soffice --convert-to pdf`: 別途 install 必要、 mac では推奨しない
4. **pandoc** + xelatex: フォント設定地獄

**Pages.app 解法**:

```bash
osascript << 'OSAEOF'
tell application "Pages"
    activate
    set theDoc to open POSIX file "/path/to/form.docx"
    delay 2
    export theDoc to POSIX file "/path/to/form.pdf" as PDF
    close theDoc saving no
end tell
OSAEOF
```

- `delay 2` は docx の Pages 内 layout 完了待ち (= 表組みや長文の場合)
- `close ... saving no` で Pages に「変更を保存しますか?」 ダイアログを出させない
- 出力 PDF は Pages の組版で render される (= Word docx と layout は厳密一致しない、 form チェック☑等は正常表示される)

### 2-5. docx fill: `python-docx` で XML 直編集 (= 共通パターン)

研究費応募・申請書類で頻出する 「☐ チェックリストと placeholder の docx を fill して PDF 化」 パターン。 `python-docx` ライブラリよりも、 zipfile + `word/document.xml` の直編集が **runtime 軽量で確実**。

**typical docx form** の構造:

- ☐ (= U+2610) と ☑ (= U+2611) はテキスト文字。 単純置換可
- placeholder `＿＿＿＿＿＿` (= 全角アンダースコア繰り返し) は単一 `<w:t>...</w:t>` run に入っていることが多い
- 識別フィールド (= 氏名・所属・部署・日付) は `<w:t>氏名：＿＿＿＿＿</w:t>` のようにラベル + placeholder が同じ run、 もしくは `<w:t>氏名</w:t>` + `<w:t>：＿＿＿＿＿</w:t>` の 2 run 分割

**実装スケルトン**:

```python
import zipfile

with zipfile.ZipFile(template_docx) as z:
    files = {n: z.read(n) for n in z.namelist()}
xml = files['word/document.xml'].decode('utf-8')

# ☐ → ☑ (= 全置換、 または位置で選択置換)
# 例: 19 個の ☐ のうち、 ある領域 (= 学生用 2 個) は ☐ 保持
boundary_start = xml.find('学生が研究代表者として応募')
boundary_end = xml.find('提出形式の確認')
out = list(xml)
for i, c in enumerate(xml):
    if c == '☐' and not (boundary_start < i < boundary_end):
        out[i] = '☑'
xml = ''.join(out)

# Placeholder 置換 (= <w:t>...</w:t> 単位)
xml = xml.replace('<w:t>＿＿＿＿＿＿＿＿＿＿＿＿</w:t>',
                  f'<w:t>{identity["name"]}</w:t>', 1)
xml = xml.replace('<w:t>所属機関：＿＿＿＿＿＿＿＿</w:t>',
                  f'<w:t>所属機関：{identity["org"]}</w:t>', 1)
# 月日: <w:t>年＿＿月＿＿日</w:t> のような複合 run
xml = xml.replace('<w:t>年＿＿月＿＿日</w:t>',
                  f'<w:t>年{month}月{day}日</w:t>', 1)

files['word/document.xml'] = xml.encode('utf-8')
with zipfile.ZipFile(dest_docx, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(name, data)
```

**事前 dump 必須**: docx の XML 構造を必ず最初に `unzip -p form.docx word/document.xml | python3 -c "..."` で grep して確認。 placeholder が `＿` 何文字か、 ラベルと placeholder が同じ run か分かれた run かを事前に把握。

### 2-6. e-Rad の使用禁止文字 (= 入力フィールド charset 制限)

e-Rad の long-textarea フィールド (= 研究目的・研究概要・経費根拠・役割分担等) は厳格な charset を強制。 以下は **エラーで弾かれる**:

| 禁止文字 | 例 | 置換 |
|---|---|---|
| 上付き・下付き数字 | `H₀` (U+2080) | `H_0` (= ASCII underscore + 数字) |
| ギリシャ文字 | `σ` `α` `μ` `β` | カタカナ「シグマ」「アルファ」「ミュー」 |
| 数学記号 | `×` (multiplication U+00D7) | `と` or `に` |
| 不等号系 | `≦` `≧` `≠` `→` | カタカナや日本語 |
| セクション記号 | `§` (U+00A7) | `第〜節` or `〜節` |
| エム・ダッシュ | `—` (U+2014) | `、` or ASCII `-` |
| 丸付き数字 | `①②③` | `(1)(2)(3)` 半角括弧 |
| ローマ数字 | `Ⅰ Ⅱ Ⅲ` | `I II III` (= ASCII) |
| 機種依存文字 | `㈱ ㈲` | `(株) (有)` |

xlsx 内部 (= 審査員が読む書類) は制限なし (= ギリシャ文字 / 下付き OK)。 制限は **e-Rad の textarea 経由でのみ**。 応募書類の draft 段階で禁止文字を排除しておくと、 xlsx と e-Rad textarea で writing convention の二重 maintenance が不要。

---

## 3. 提案書を音声で確認 (macOS `say` で TTS)

長文 (= 6 セクション数千字) を視覚読みで疲れた時、 macOS 標準の `say` で TTS して耳で確認。

```bash
say -v "Kyoko (Enhanced)" -r 200 "本研究の目的は..."
```

- 日本語音声: `Kyoko` (女性) / `Otoya` (男性)、 各 Enhanced 版が高音質
- `-r 200` は WPM (Words Per Minute)、 200 が読み上げに自然なペース
- 長文を sections で区切って速報生成: `bash` script で `say` を順次呼ぶと中断 (`killall say`) しやすい
- 数式記号や英略語 (LLM、 H₀、 EJP-C 等) は読みづらいので script で読みやすく書き換え (例: `H₀` → `エイチゼロ`)

提案書 self-review 用途では、 自分で書いた文章の「不自然な日本語」 が聞いて初めてバレることが多い。

---

## 4. 共通の規律

### 4-1. xlsx 内部の cell 構造を **常に最初に dump** する

書き込む前に必ず `ws.iter_rows()` で全 cell + alignment + merged cells を出力して構造を把握する。「label cell」 と「input cell」 の混在、 merged cells、 dropdown validation 等、 form ごとに layout が異なる。 推測で `B6` に書こうとしたら実際は `B6:I6` merged で input は `B6` だけだった、 などが起きる。

### 4-2. 字数制限は cell 末尾の formula で常時確認

form template が `=LEN(A3)` のような counter cell を持っていることが多い。 fill 後に該当 cell の値を読んで `0 < count <= limit` を assertion する pipeline にする。

### 4-3. user 視覚確認は computer-use ではなく user に依頼

GUI 確認は MCP round-trip より user の直接視認が **常に速い**。 詳細: `~/Claude/odakin-prefs/work-discipline.md §視覚確認は user に依頼する` (個人層のため public には記述薄め、 一般則は本節の通り)。

---

## 5. 関連リポ

- 実例: `~/Claude/grant-applications/applications/2026-jst-spread/fill_xlsx.py` (SPReAD 様式 1 fill)
- docx 自動 fill 実例: `~/Claude/grant-applications/applications/2026-jst-spread/fill_forms.py` (SPReAD 様式 0 + 様式 2 fill、 §2-5 のリファレンス実装)
- ヘルパ抽出元: 同上 `fit_cell` 関数 (内部、 上記 §1-4 のリファレンス実装)
- 業績選定の連携先: `~/Claude/physics-research/papers/grant_pubs.py` (INSPIRE 連携)

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

### 1-11. Excel の行高さ上限は 409pt — これを超えると視覚的に「非表示」 化する

**症状**: 行高さに 591.5pt や 2754pt 等の極端な値が入った xlsx を Excel で開くと、 周囲の行が「非表示扱い」 のように見える (= 巨大行が画面を占有し、 viewport 内で他の行が visible にならない)。 reviewer (= 事務担当者) から「行 N-M が非表示になっている」 と指摘される。

**原因**: Excel の行高さ MAX = **409pt** (= ~545 px @ 96 dpi、 ~14 cm)。 openpyxl は値を strict 検証しないため 409pt を超えても save できるが、 Excel で開くと表示が異常になる。 ユーザー直接編集時の auto-resize (= 長文 + wrap_text=True で row 高さが自動拡大) で意図せず 409pt 超過に陥るケース多し。

**正しい解法**: row height は内容量から論理計算した値を **409pt 以内** に収める。 §1-4 `fit_cell` 計算式を使えば自動的に reasonable な値になるが、 既に巨大値が入った xlsx を inherit する場合は再計算で明示 reset:

```python
# 既存の超過 row height を reset
for r in range(1, ws.max_row + 1):
    h = ws.row_dimensions[r].height
    if h and h > 409:
        ws.row_dimensions[r].height = min(409, _calc_height_for_cell(ws, r))
```

origin: 2026-05-14 JST SPReAD で 行 22 = 591.5pt / 行 26 = 2754pt の状態が「行 20-22 が非表示」 として事務担当者から指摘 → 行 22 = 30pt / 行 26 = 150pt に reset で修復。

### 1-12. sheetView.topLeftCell の scroll 位置 persistence

**症状**: 提出した xlsx を reviewer が開くと、 ファイルの先頭ではなく中間行 (= A17 等) から表示される。 reviewer が「先頭が表示されない、 内容が欠けている」 と誤解する。

**原因**: xlsx の sheet metadata に `<sheetView topLeftCell="A17">` が記録されている。 これは Excel/openpyxl で「最後にユーザーが scroll した位置」 を保存する仕様で、 file 保存時に巨大行 (= §1-11) が view を占めていたとき、 viewport 起点が下方に固定される。 template 配布者が「入力位置にスクロール済」 で配布する慣習もあるが、 reviewer 視点では先頭から見たい。

**正しい解法**: 提出前に topLeftCell を A1 に reset:

```python
for sname in wb.sheetnames:
    wb[sname].sheet_view.topLeftCell = "A1"
```

または最初の submission で行高 (= §1-11) を適切化していれば、 topLeftCell も自然に A1 のままになる (= scroll 履歴が template 配布時点のまま)。

origin: 2026-05-14 JST SPReAD で「行 20-22 が非表示」 指摘と同時に発覚。 topLeftCell="A17" のままだと先頭の研究者情報行 (= 行 6-15) が viewport 外で「行を欠落して提出された」 と誤読される risk。

### 1-13. xlsx rich text formatting (= 部分 underline / bold / italic)

行政・学術 様式 で「**著者 (本人に下線)**」 「**重要部分は太字**」 等の要件がある場合、 セル内の特定文字列だけに format を適用する必要がある。 openpyxl では **`CellRichText` + `TextBlock` + `InlineFont`** で実装。

```python
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

# Run-level font specs (= 同じ font name / size、 装飾だけ差し替え)
plain = InlineFont(rFont="ＭＳ Ｐゴシック", sz=10)
underlined = InlineFont(rFont="ＭＳ Ｐゴシック", sz=10, u="single")
bold = InlineFont(rFont="ＭＳ Ｐゴシック", sz=10, b=True)

# Build the rich text from alternating runs (= 業績欄の例、 本人氏名のみ下線)
# cell.value (= 例): "C1, C2 and SELF, \"Title A\", J1 ... \nC3, SELF and C4, \"Title B\", J2 ..."
TARGET = "<applicant-name>"  # = 提出者の姓 or イニシャル (form の表記に合わせる)
parts, remaining = [], cell.value
while True:
    idx = remaining.find(TARGET)
    if idx < 0:
        if remaining: parts.append(TextBlock(plain, remaining))
        break
    if idx > 0: parts.append(TextBlock(plain, remaining[:idx]))
    parts.append(TextBlock(underlined, TARGET))
    remaining = remaining[idx + len(TARGET):]
cell.value = CellRichText(parts)
```

**重要 caveat — openpyxl readback の flatten bug**: 上記で書いた xlsx を後で `cell.value` で read back すると **`str` 型に flatten される** (= rich text の run 構造が見えない)。 format が正しく保存されたかを verify するには **xlsx の生 XML を unzip → `xl/worksheets/sheetN.xml` で `<u val="single"/>` 等を grep** する:

```python
import zipfile, re
with zipfile.ZipFile(xlsx_path) as z:
    xml = z.read("xl/worksheets/sheet4.xml").decode("utf-8")
underline_runs = re.findall(r'<u val="single"/>[^<]*</rPr><t[^>]*>([^<]+)</t>', xml)
print(f"Underlined runs: {underline_runs}")  # ['<applicant-initial>', '<applicant-initial>', ...]
```

xlsx XML の文字エンコード形式: ＭＳ Ｐゴシック等の全角文字は `&#65325;&#65331;` 等の numeric character reference にされる。 visual diff には decode しなければ読みにくい。

origin: 2026-05-14 JST SPReAD 様式 1 Sheet 2 A15 (研究業績欄) で提出者本人氏名 (= 業績 5 件すべて) に underline を rich text で適用。 readback は str だったが xlsx 内部 XML 上で `<u val="single"/>` × 5 個 確認で OK 検証。

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

### 2-7. 「署名」 要求は手書き署名 or 電子署名、 認印画像では不可

行政・学術 様式 (= 助成金応募同意確認書、 推薦書、 法的同意書等) で「**署名 又は 電子署名**」 「**本人が署名**」 と明記された欄に、 認印 (= 朱印 PNG) を貼っても reject される。 「電子署名 (e-signature)」 が広義に「電子的に署名処理されたもの」 と解釈されるため認印画像で代替できそうに見えるが、 実務上 reviewer は **手書き署名 (= scan された自筆画像) または 電子署名 cert 付き PDF** を期待する。

**対処**: 自筆署名 (= 紙に署名 → scan or タブレット → 透過 PNG) を準備して docx 氏名欄に挿入:

```python
from docx.shared import Inches
for p in doc.paragraphs:
    if p.text.startswith('氏名') and ('<surname>' in p.text or '＿' in p.text):
        p.add_run('  ')  # spacer
        p.add_run().add_picture(str(SIGNATURE_PNG), width=Inches(1.8))
        break
```

幅 1.8 inch (= ~4.5 cm) が標準的な「署名らしい」 サイズ。 0.5 inch だと縮小されすぎて読めない。

**認印 (= 朱印) との使い分け**:
- 「印 / 印鑑 / 認印」 が要求 → hanko PNG (= 朱印) で可
- 「署名 / 電子署名 / 本人署名」 が要求 → **signature PNG (= 手書き) 必須**

個人 user は事前に両方準備しておく (= 個人層 layer に置く)。

origin: 2026-05-14 JST SPReAD 様式 0 + 様式 2 の氏名欄、 当初 hanko を挿入 → 「電子署名必要」 と事務担当者から電話指摘 → signature PNG に差替えて再提出。

### 2-8. docx template の placeholder 末尾装飾 underscore の cleanup

**症状**: docx form template の placeholder (= `氏名：＿＿＿＿＿＿＿＿＿＿＿＿＿`) を python-docx 経由で置換 (例: 12 個の `＿` を name に) しても、 **末尾に 1〜2 個の trailing underscore run** が残る。 結果: `氏名: <提出者氏名>＿` のように半端な `＿` が残って見栄え悪化。

**原因**: 雛形が「装飾用 placeholder = 12 個」 + 「trailing 装飾 = 別 run の 1〜2 個」 で構成されている。 単純な `xml.replace('<w:t>＿＿＿＿＿＿＿＿＿＿＿＿</w:t>', f'<w:t>{name}</w:t>')` では 12 個 run しか置換されず、 trailing run が残る。 XML 上では:

```xml
<w:r><w:t>氏名：</w:t></w:r>
<w:r><w:t>＿＿＿＿＿＿＿＿＿＿＿＿</w:t></w:r>   ← 置換対象 (12 個)
<w:r><w:t>＿</w:t></w:r>                            ← 残る (装飾 trailing、 1 個)
```

**対処**: placeholder 置換後、 trailing run を別途除去:

```python
xml = xml.replace('<w:t>＿</w:t>', '<w:t></w:t>', 1)        # trailing 全角 1 個 (= 氏名後)
xml = xml.replace('<w:t>__</w:t>', '<w:t></w:t>')           # trailing 半角 2 個 (= 所属/部署後、 計 2 箇所、 全削除)
```

各 form template ごとに trailing pattern が違うので、 dump で全 `<w:t>` を出力して目視確認後に置換 pattern を確定。

origin: 2026-05-14 JST SPReAD 様式 0 で発覚 (= 「氏名: <提出者氏名>＿」 という末尾装飾 _ が user 視覚に悪い印象を与えると指摘) → 上記 cleanup を fill_forms に追加。 様式 2 は trailing 装飾を持たない雛形だったため変更不要。

### 2-9. docx → PDF の page count 圧縮 (= 余白縮小 + 行間 + 末尾空段落削除)

事務指定で「1 ページ / 2 ページに収める」 が要件の docx (= チェックリスト・同意書) は、 default レイアウト (= margin 0.5 inch、 line_spacing 1.0、 末尾空段落多数) のままだと自動的に複数ページに割れる。

**python-docx で行う 3 段階圧縮**:

```python
from docx.shared import Inches, Pt

# 1. Margin 縮小
for sec in doc.sections:
    sec.top_margin = Inches(0.3)
    sec.bottom_margin = Inches(0.3)
    sec.left_margin = Inches(0.4)
    sec.right_margin = Inches(0.4)

# 2. Line spacing 0.9 + 空段落の上下 spacing 削除
for p in doc.paragraphs:
    pf = p.paragraph_format
    pf.line_spacing = 0.9
    if not p.text.strip():
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)

# 3. 末尾の連続空段落を削除 (= page break trigger の主因)
while doc.paragraphs and not doc.paragraphs[-1].text.strip():
    p = doc.paragraphs[-1]
    p._element.getparent().remove(p._element)
```

経験値:
- margin 0.5 → 0.3 inch で ~22pt (= 0.3 inch = ~22pt) ずつ vertical space 増加 (= 上下計 ~44pt)
- line_spacing 1.0 → 0.9 で 30 行に対し ~30pt 短縮 (= 1pt × 10% × 30)
- 末尾空段落 3 個 削除で ~36pt 短縮 (= 12pt × 3)
- 計 ~110pt 圧縮 → 2 page → 1 page を実現可能

これでも収まらない場合は font_size を 10pt → 9.5pt に下げる (但し可読性低下)。

origin: 2026-05-14 JST SPReAD で 様式 0 = 2 → 1 page、 様式 2 = 3 → 2 page を上記 3 段階で達成。

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

## 5. **label vs input row anti-pattern** (= 様式 改変 の主因)

行政・学術 様式 xlsx の頻発バグ。 **記入前に必ず読む**。

### 5-1. 構造

日本の公的 様式 xlsx は section ごとに以下の 2 行 pair で組まれる:

```
Row N:    "<セクション名>の必要性" / "<セクション名>の明細"   ← pre-printed LABEL
Row N+1:  (空白、 列方向に merged)                        ← 記入位置
```

例 (= 2026-05 JST SPReAD 様式 1 研究計画調書 Sheet 3):

| 行 | 内容 | role |
|---|---|---|
| 9  | "総計" | label |
| **10** | **"設備備品費、消耗品費の必要性"** | **label (pre-printed)** |
| 11 | (empty, A11:G11 merged) | **input — 記入はここ** |
| 18 | "謝金、旅費の必要性" | label |
| 19 | (empty) | input |
| 28 | "その他の必要性" | label |
| 29 | (empty) | input |

### 5-2. 典型バグ (= 様式改変)

label cell に narrative を直接書き込んでしまう (= overwriting the pre-printed label)。

**原因 (= reflexive form-fill)**:
- label テキストが「section title なので、 ここに content を書け」 と読めてしまう
- 真の入力行 (N+1) は empty に見えて「未使用 cell」 と誤解する
- Excel は label vs input を視覚的に区別する style 付けをしない (= 同じ font、 同じ border)
- merged input cell が大きく開いていても「装飾の空き」 にしか見えない

**実害**:
- 提出後に審査機関 (= 教育研究支援課等) から 「**①様式の改変**」 として差戻し
- ファイル単位の reject や再提出処理コスト
- 2026-05-13 JST SPReAD で 提出者が同 pattern で 3 箇所 (= Sheet 3 行 10/18/28) で発生、 所属機関の事務担当者から指摘で発覚。 提出者申告では prior form fill でも同 pattern を起こしていた (= 再発 pattern)

### 5-3. 機械的検出: `diff-form-xlsx.py`

`claude-config/scripts/diff-form-xlsx.py` で雛形と提出版を全 cell diff し、 label 上書きを検出。

```bash
python3 ~/Claude/claude-config/scripts/diff-form-xlsx.py \
    /path/to/filled.xlsx \
    /path/to/template.xlsx
```

- **`LABEL_OVERWRITE`** (= critical): 雛形に「〜の必要性 / 〜の明細 / 〜について」 等の label-like text があり、 提出版がそれを別 text で上書き
- **`LABEL_DELETED`** (= critical): label が空になっている
- **`INPUT_FILLED`** (= info): 雛形 empty → 提出版 fill (= 正常)
- **`VALUE_CHANGED`** (= info): その他の変更 (= placeholder 置換等)

critical 検出時は exit code 1。 提出前 / commit 前に必ず実行する pipeline にする。

label 判定は heuristic で suffix 一致 (= `の必要性 / の明細 / について / の内容 / の確認 / の有無 / の状況`)。 新しい雛形で別 suffix が現れたら script の `LABEL_SUFFIXES` に追記する。

### 5-4. 予防 workflow (= 規律)

1. **§0 dump で template の構造を **必ず** 最初に把握** (= label 行 と input 行 を **目視で特定** 後に fill code 書く)
2. fill code 内で **label 行に対する write は禁止**。 input 行 (= N+1) にのみ write
3. **fill 後に `diff-form-xlsx.py` を実行** して mechanical 検証 (= 人間目視が missed cell を catch)
4. critical 検出時は、 label を template から restore + narrative を N+1 行に move

### 5-5. label 内 embedded instruction の見落とし防止

label cell には input cell に対する **embedded instruction** が書かれていることがある。 例 (= JST SPReAD 様式 1 から):

- 「研究業績等\n※ ... **著者（本人に下線）**...」 → input cell で本人氏名を rich text underline 必須
- 「研究目的(日本語：**80 文字以上 400 文字以内**)」 → input cell で字数制限を守る
- 「e-Rad 研究者番号 (**8 桁の半角数字**)」 → input cell は半角数字 8 桁
- 「氏名 ※姓と名は **全角で 1 スペース空ける**」 → 全角空白挿入

これらは label 全文を読まないと拾えない (= 多くは ※ marker 以降の長い注記内)、 短い label 部分だけで input cell を fill すると見落とす。

**機械的検出**: `claude-config/scripts/scan-form-instructions.py <xlsx>` で xlsx 全 cell から instruction keyword を抽出し category 別 (= format / charset / limit / structure / attachment / auth) に group 表示:

```bash
python3 ~/Claude/claude-config/scripts/scan-form-instructions.py /path/to/form.xlsx
```

検出 keyword 例:
- format: 「下線」 / 「本人に下線」 / 「太字」 / 「斜体」 → rich text 適用必要
- charset: 「半角数字」 / 「半角英数字」 / 「全角」 → 文字種チェック
- limit: 「字以内」 / 「字程度」 / 「最大」 → 字数 / 件数チェック
- structure: 「改行」 / 「箇条書き」 → 構造化
- attachment: 「別紙」 / 「別添」 → 別ファイル提出
- auth: 「署名」 / 「電子署名」 / 「印鑑」 / 「認印」 → 認証要素

**運用**: 提出前に scan を回し、 各 instruction が input cell に反映されているかを user/Claude が手動 verify。 keyword 検出は informational (= critical/non-critical 判定なし、 exit 0)。

origin: 2026-05-14 JST SPReAD で「本人氏名に下線」 (= 様式 1 Sheet 2 A14 ラベル内) を見落として複数回再提出。 A14 ラベル全文 (= 80 字 truncate せず) を読んでいれば検出できた典型例。

### 5-6. dump 段階での label 識別

§0 の `dump_form.py` 出力時、 各 cell が label か input かを mark するヘルパ:

```python
# dump_form.py の cell loop 内に追加
label_marker = " [LABEL?]" if isinstance(c.value, str) and any(
    c.value.strip().endswith(s) for s in ("の必要性", "の明細", "について", "の内容", "の確認")
) else ""
print(f"  {c.coordinate} (...): {v}{label_marker}")
```

dump 時点で label が浮き上がる → fill 対象から自動的に除外する判断が容易になる。

---

## 6. 関連リポ

- 実例: ある grant 申請 repo の specific 助成事業 dir 内の `fill_xlsx.py` (= 様式 1 xlsx 自動 fill)
- docx 自動 fill 実例: 同 dir の `fill_forms.py` (= 様式 0 + 様式 2 docx fill、 §2-5 のリファレンス実装)
- ヘルパ抽出元: 同上 `fit_cell` 関数 (内部、 上記 §1-4 のリファレンス実装)
- 業績選定の連携先: `~/Claude/physics-research/papers/grant_pubs.py` (INSPIRE 連携)

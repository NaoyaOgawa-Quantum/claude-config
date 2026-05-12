# Office automation (macOS): xlsx form fill, PDF conversion, TTS review

研究費応募書類 / 教務書類 / 学術様式の Excel xlsx を **openpyxl で fill する作業**、 および生成物の **PDF 化 / 印刷 / 音声読み上げ** に関する規約と落とし穴集。

origin: 2026-05 SPReAD (AI for Science 萌芽的挑戦研究創出事業) 応募で得た知見 (= 様式 1 研究計画調書 xlsx の Python 自動 fill、 figure 埋め込み、 字数制限管理、 PDF snapshot 生成、 TTS 確認)。

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
- ヘルパ抽出元: 同上 `fit_cell` 関数 (内部、 上記 §1-4 のリファレンス実装)
- 業績選定の連携先: `~/Claude/physics-research/papers/grant_pubs.py` (INSPIRE 連携)

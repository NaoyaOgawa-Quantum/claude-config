# Google API を Python から直接アクセスする setup

MCP では cover できない (= bulk 操作・xlsx parse・特殊 scope) Google API call を Python から直接行うときの setup と運用規約。 個別 MCP (Gmail / Calendar / Classroom 等) と並存して動かす想定。 CLAUDE.md から参照: `~/Claude/claude-config/conventions/google-api-direct-access.md`

関連: `conventions/mcp.md §「MCP で不十分な場合: API 直接アクセス」` (= 使い分け基準)、 `conventions/google-url.md §「GCP project 管理操作の特殊性」` (= URL 規約)。

## 全体像 (= 3 layer)

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: GCP project (= 全 owner 操作の単位)               │
│   project_id / project_number / owner email                 │
│   各 API は project レベルで個別 enable 必要 (Sheets/Drive)│
│   project owner にしか API enable・OAuth client 編集不可    │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: OAuth client (= consent UI を出す主体)            │
│   1 つの GCP project に複数 OAuth client 可、 通常 1 つで充分│
│   gcp-oauth.keys.json を file system に保管                 │
│   複数アカウント (個人 + Workspace) の token 発行に共有可  │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Account token (= 各 Google アカウントの承諾結果) │
│   {account}-credentials.json として保管 (= access + refresh)│
│   scope 別に複数 token 並存可 (= Gmail scope vs Sheets scope)│
│   refresh_token で永続使用、 access_token は自動更新       │
└─────────────────────────────────────────────────────────────┘
```

**重要な区別**: project 管理 (= layer 1) と token 発行 (= layer 3) は別 layer。 owner アカウント (= layer 1) が個人 Google で、 token 発行 (= layer 3) を Workspace アカウントで行う構成は normal。

## GCP project の API enable

各 Google API (Gmail / Sheets / Drive / Calendar / Classroom / etc.) は GCP project ごとに**個別 enable 必要**。 1 つ enable しても他は別。

**URL 規約** (= `conventions/google-url.md §「GCP project 管理操作の特殊性」`):
```
https://console.developers.google.com/apis/api/{api}.googleapis.com/overview?project={projectNumber}&authuser=<project_owner_email>
```

- `authuser=` は project owner のメールアドレス。 active account が違うと「project が見つかりません」 で弾かれる
- API enable 後は **propagate 5-10 分** かかる場合あり (= typical は 1-2 分、 上限近い retry が必要なケースあり)。 立て続けに 403 `SERVICE_DISABLED` が返るのは propagate 待ち中の signal

**propagate 中の polling pattern** (Bash で背景 retry):
```bash
until python3 -c "<API call test>; sys.exit(0)" 2>/dev/null; do
  echo "$(date +%H:%M:%S) - not yet, sleeping 30s..."; sleep 30
done
```

通れば background 完了通知が返る。 sleep 90 のような単発長 sleep は harness が block するケースあり、 until-loop で polling する。

## OAuth scope の設計

### scope を最小化する原則

各 token は **必要最小限の scope** で発行する。 Drive 全体読み放題の `drive.readonly` よりも `drive.metadata.readonly` (= ファイル名・サイズ等のみ) や `drive.file` (= picker UI で grant されたファイルのみ) を優先。

ただし**読みたい対象が xlsx (= Office file) を含む**場合は `drive.readonly` が必須 (= `drive.metadata.readonly` では binary download 不可)。 Sheets native のみなら `spreadsheets.readonly` で済む。

### 既存 OAuth client に scope 追加 vs 新規 client

| 選択 | Pros | Cons |
|---|---|---|
| 既存 client + 既存 token に scope 追加 | OAuth client が 1 つで管理シンプル | 全 token が scope 拡大、 影響範囲不明、 既存 token は再 reauth 必要 |
| 既存 client + 別 scope set で新 token (separate directory) | 既存 token に影響なし、 用途別に独立 | directory + reauth 1 回ずつ、 token が増える |
| 新 OAuth client + 新 token | 完全独立 | GCP コンソールで client 作成必要、 user 承諾の consent screen も別物 |

**推奨**: 既存 client + 別 directory + 別 scope token (= 中段)。 既存 MCP の動作に影響を与えず、 用途別に独立管理。

### scope 増やし方の手順

1. 新 directory を `<mcp-config-repo>/<service>/` に作成 (例: `sheets/`)
2. `gcp-oauth.keys.json` を既存 directory (= 同じ GCP project の OAuth client) からコピー
3. `auth.mjs` (node.js) または auth Python script を作成
   - SCOPES を必要分のみ列挙
   - 既存 directory と被らない localhost port (e.g. 8370/8371/8372 → 新規 8373)
   - login_hint に対象アカウントを指定
4. node auth.mjs 実行 → ブラウザで承諾 → callback で token 保存
5. token は git-crypt で encrypt して commit (= `.gitattributes` で filter=git-crypt 指定)

### Scope 不足の error message

```
HttpError 403: ... insufficient_scope ...
```

→ scope 追加 + reauth が必要。 既存 token を上書きする (= 同じ credentials.json path を再書き込み)。

## mimeType による分岐 (= Sheets vs xlsx)

Google Drive 上のスプレッドシートには 2 形式がある:

| mimeType | 形式 | 読み方 |
|---|---|---|
| `application/vnd.google-apps.spreadsheet` | Google Sheets native | Sheets API (`spreadsheets().values().get`) |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | xlsx (= Excel アップロード) | Drive API `files().get_media` で download → `openpyxl` で parse |
| `application/vnd.ms-excel` | xls (= 旧 Excel) | Drive API download → `xlrd` 等で parse (= openpyxl 不可) |

**Sheets API は xlsx に対して `FAILED_PRECONDITION` を返す** (= "The document must not be an Office file.")。 mimeType を見て分岐する code path が必要。

**URL からの事前 hint**: 共有 URL に `?rtpof=true&sd=true` が付いている = 「Retain the original format」 = xlsx (= 元 file 形式を保持して開いている) の signal。

### Pattern: 統一 reader

```python
drive = build("drive", "v3", credentials=creds, cache_discovery=False)
meta = drive.files().get(fileId=file_id, fields="mimeType,name").execute()
mime = meta["mimeType"]

if mime == "application/vnd.google-apps.spreadsheet":
    # Sheets API
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    data = sheets.spreadsheets().values().get(spreadsheetId=file_id, range="A1:Z500").execute()
elif mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
    # Drive download + openpyxl parse
    import io, openpyxl
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, drive.files().get_media(fileId=file_id))
    done = False
    while not done: _, done = downloader.next_chunk()
    buf.seek(0)
    wb = openpyxl.load_workbook(buf, data_only=True)
    # wb.sheetnames + wb[name].iter_rows(values_only=True)
```

## Token refresh の運用

`google-auth` の `Credentials.refresh(Request())` で access_token を自動更新する。 refresh_token は通常 rotate しないが、 まれに Google 側で rotate される場合あり (= 7 日以上の長期未使用後等)。 rotate された場合は古い token が invalid_grant になるので、 再 reauth が必要。

実装パターン:
```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

creds = Credentials(
    token=tok["access_token"], refresh_token=tok["refresh_token"],
    token_uri=oauth["token_uri"], client_id=oauth["client_id"],
    client_secret=oauth["client_secret"], scopes=tok["scope"].split(" "),
)
if not creds.valid:
    creds.refresh(Request())
# 必要なら更新後の creds.token / creds.expiry を file に書き戻す
```

MCP server と Python script の同時実行で refresh が競合する可能性は理論上ある (= 両方が同時に refresh を試みて、 Google が新 refresh_token を rotate した瞬間に片方が古い token をファイルに書き戻す)。 実害は希だが、 long-running script 中は MCP 経由の同 account 操作を避けるのが安全。

## documentation の義務

GCP project に紐づく以下の情報は**個人層 (= layer 3) の secrets-related docs に明記**しておく:

- **project owner email**: 管理操作 (API enable / OAuth client / quota / billing) に使うアカウント
- **project_id + project_number**: URL 組み立てに使う stable identifier
- **enable 済 API のリスト**: 新 setup 時の参考、 API 追加時の更新対象
- **OAuth client 共有 status**: 同じ client を複数 directory (e.g. gmail-mcp + calendar + classroom + sheets) で使い回す pattern なら、 client rotate 時の影響範囲

これがないと、 multi-account 持ち user / Claude が「どのアカウントで GCP コンソール開けばいいか」 で繰り返し混乱する。 owner email は public docs (= claude-config 等) では PII になるので、 個人層に書く。

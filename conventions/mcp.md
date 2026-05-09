# MCP 規約

MCP ツールを使うリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/mcp.md`

## 共通（CONVENTIONS.md §5.7 の手順詳細）

- **確認方法**: Gmail は `gmail_get_profile`、Calendar は `gcal_list_calendars` で接続先アカウントを確認
- **複数 MCP がある場合**: セッションの deferred tools 一覧で同一サービスの MCP が何個あるか確認し、それぞれ `get_profile` を実行して UUID→アカウントの対応を把握する
- **UUID→アカウント対応表は MCP 設定リポに保持**: 各 MCP 設定リポ (例: `gmail-mcp-config`) の CLAUDE.md または SESSION.md に UUID→アカウントの対応を記録する。memory には書かない (machine-local で cross-machine 不整合を招く。詳細: [docs/convention-design-principles.md §5](../docs/convention-design-principles.md))。新規セッションで対応表が不明・古ければ、全 MCP で `get_profile` を実行して deferred tools の UUID 一覧と照合し、差分を MCP 設定リポに追記する
- **アカウント一覧の正本**: 各 MCP 設定リポの CLAUDE.md を参照（各プロジェクトリポの CLAUDE.md にはハードコードしない）

## `claude mcp` の project 解決ルール (注意)

`claude mcp add` / `claude mcp remove` の default scope は **local** = 「対象 Claude Code project 内の MCP 登録」(`~/.claude.json` の `projects[<path>].mcpServers` 配下)。"対象 project" は cwd ではなく **cwd から ancestor を辿って最初に見つかる `.claude/` を持つディレクトリ** で決まる (= claude CLI が project と認識するディレクトリ)。

セットアップ用の bash スクリプト等が、**自分自身のリポ内**から `claude mcp` を呼ぶと、登録先が想定外の project に入る:

- 期待: `~/Claude` project に gmail server を登録
- 実態: スクリプトが `~/Claude/gmail-mcp-config/` 配下から走り、`~/Claude/gmail-mcp-config/.claude/` を最寄り `.claude/` として resolve → 登録先が `gmail-mcp-config` project になる

回避策:

- スクリプト冒頭で target project に **明示的に `cd`** してから `claude mcp` を呼ぶ。target は引数 / 環境変数で受け取れるようにしておく (cwd 暗黙依存をなくす)
- あるいは `--scope user` で全 project 共通の user-level 登録にする (per-project 登録にしたい場合は不向き)

設置時 / 撤去時の冪等化 (`claude mcp remove "<name>" 2>/dev/null || true; claude mcp add ...`) は target project が正しいときに初めて意味を持つので、target 解決を先に固める。

## MCP 接続失敗時のセッション内復旧 (runbook)

session 中に MCP server が `Failed to connect` / `disconnected` 状態になったときの対応手順。**Claude Code の設計上、stdio MCP server は session 起動時に bind されており、起動時に接続失敗するとそのセッション内で再接続する built-in 経路がない** (上流既知 bug、GitHub claude-code issues #20684, #33468 参照)。HTTP/SSE 系は exponential backoff で auto-retry するが、stdio は手動。以下、軽い順に試す:

### 0. 状態確認

```bash
# 全 MCP の現状
claude mcp list           # ✓ Connected / ✗ Failed to connect

# 該当 server の詳細 (登録 args / env)
claude mcp get <server-name>
```

`claude mcp list` の "Connected" は **session 起動時の bind 結果**で、その後 server が落ちても更新されない場合がある。実際のツール呼び出しが通るかどうかが真の動作確認。

### 1. 該当 server を素手で立ち上げて handshake 通る確認

stdio server の場合、生 stdio で `initialize` リクエストを投げて応答するか確認:

```bash
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' | \
  env <NEEDED_ENV_VARS> node /path/to/server.mjs
```

応答に `"result":{"protocolVersion":...}` が返れば server 側は健全。問題は Claude Code の MCP daemon 側の cache。

### 2. log を確認

```bash
ls -t ~/Library/Caches/claude-cli-nodejs/-Users-odakin-Claude/mcp-logs-<server>/ | head -3
cat ~/Library/Caches/claude-cli-nodejs/-Users-odakin-Claude/mcp-logs-<server>/$(ls -t ~/Library/Caches/claude-cli-nodejs/-Users-odakin-Claude/mcp-logs-<server>/ | head -1)
```

`Successfully connected` で終わっていれば session 起動時は OK だった = mid-session で落ちた。`timeout` / `stderr` で終わっていれば起動時失敗。

### 3. remove + re-add で再登録 (transient 失敗のリトライ誘発)

```bash
cd ~/Claude  # ★ ~/Claude project scope 必須
claude mcp remove <server-name> -s local
claude mcp add <server-name> \
  -e KEY1=VALUE1 -e KEY2=VALUE2 \
  -- <command> <args...>
```

env vars と args は `claude mcp get` で取った内容を再投入。再登録後、**少し待ってから (10-30s)** ToolSearch で当該 MCP の tool schema を取得し直す:

```
ToolSearch select:mcp__<server>__<tool>
```

実際に tool を呼んでみる。MCP daemon が新登録を pick up していれば動く。

### 4. `/mcp` slash command (status 確認のみ、reconnect ボタンなし)

Claude for Mac の Code タブで `/mcp` を打つと UI 一覧が出る。**stdio server の reconnect/restart アクションは無い** (上流バグ #33468 で feature request 中)。HTTP/SSE は auto-retry 進捗が見える。status 確認用途のみ。

### 5. `claude --resume` で session 再起動 (最終手段)

ステップ 0-4 で復旧しなければ:

```bash
# 1. Claude for Mac を Cmd+Q または Code タブを閉じる
# 2. 元の作業ディレクトリで:
cd ~/Claude/<project>
claude --resume
```

session の会話 / context / tool 許可は **保たれる**。MCP server だけ再起動から bind し直される。stdio server の起動時失敗が transient だったなら今度は通る。**ただし起動時失敗が決定論的 (env / 設定不備) なら何度試しても同じ** → 設定を直してから resume。

### 6. それでも動かない場合の根本原因別 checklist

- **環境変数の missing**: MCP server は Claude Code 起動時の minimal env を継承する。`$PATH` / `$NODE_OPTIONS` / カスタム credential path 等。`-e KEY=VALUE` で明示的に渡す
- **working directory**: stdio server は Claude Code の cwd を継承。絶対パスで file を参照する設計が安全
- **credential lock 競合**: OAuth token file を読む系の server が、別プロセス (Python script 等) と同時に lock を取りに行くと timeout。MCP 起動と batch script の同時実行を避ける
- **cold-start タイムアウト**: googleapis 等の重い import で 2-3 sec かかる。MCP daemon の timeout (30s) には収まるが、複数 server 同時起動で IO 競合があると押し出される。重い server は esbuild 等で single-file bundle を試す

### Chrome MCP (Claude in Chrome) の特殊事情

Chrome MCP は `claude mcp` 配下ではなく **Claude.app の Chrome extension 経由** で別経路。`claude mcp list` には出ない。復旧:

1. Chrome で `chrome://extensions/` → Claude 拡張のトグル OFF → ON で reload
2. または Chrome を quit + 再起動
3. 上記でダメなら Mac app (Claude.app) も quit + 再起動

### 過去事例

- **2026-05-01**: classroom-cis (stdio) が session 中に disconnected。server.mjs 単独 stdio handshake は OK、log は `Successfully connected` で終わる (落ちた時刻のログなし)。`claude mcp remove + add` で再登録 → 数分後に ToolSearch + tool 呼び出し成功。Mac app は quit せず session 維持で復旧した sample。同時に gmail-* 4 server も system-reminder で disconnected と告知されたが、こちらは自動で再接続成功 (stdio でも `@gongrzhe` の MCP は graceful reconnect 機構を持つ模様)。Chrome MCP は別 incident で接続不可、Mac app 側の対応必要。

## MCP 設定リポの役割

MCP サーバーの認証情報やセットアップ手順を一箇所で管理するためのリポ。複数のプロジェクトが同じ MCP サーバー（Gmail、Calendar 等）を利用する場合、認証情報の管理を各プロジェクトに分散させると更新漏れや不整合が起きる。設定リポに集約することで、アカウント追加・トークン更新・サーバー移行等の変更が1箇所で完結する。

記録すべき内容:
- アカウント一覧と認証情報の保存場所
- MCP サーバーの選定理由（DESIGN.md）
- セットアップ・再認証の手順（スクリプト化推奨）
- OAuth スコープと制約
- 認証情報のバックアップ方針

MCP 設定リポは private にすること（認証情報のパスやアカウント構成を含むため）。認証情報そのものはリポ外（例: `~/.gmail-mcp/`）に置き、リポには構造とスクリプトだけを入れる。

---

## MCP で不十分な場合: API 直接アクセス

MCP ツールは個別操作に最適だが、バッチ操作（一括削除・ラベル付け・統計取得等）には向かない。Gmail MCP の `modify_email` は1件ずつだが、Gmail API の `batchModify` は1回で最大1000件を処理できる。

**基本的な考え方:** MCP サーバーが OAuth 認証情報をローカルに保持しているなら、同じ認証情報を Python（`google-api-python-client`）から直接利用できる。新規に OAuth フローを構築する必要はない。

### 使い分けの基準

| 操作 | 手段 | 理由 |
|---|---|---|
| メール1件の読み取り・返信 | MCP | 対話的操作に最適、Claude が直接呼べる |
| 一括操作（削除、ラベル付け等） | Python + API | `batchModify`/`batchDelete` で最大1000件/回 |
| 統計・分析（件数、容量等） | Python + API | `messages.list` + 集計が柔軟 |
| フィルター管理 | Python + API | MCP にフィルター API がない |
| 確実な thread continuity (`In-Reply-To` 付きの返信送信) | Python + API | 多くの Gmail MCP 実装は `read_email` の戻り値に `Message-ID` ヘッダを含めないため、MCP 単独で `inReplyTo` パラメータを組み立てられない。`messages.get(format='full')` で全 headers 取得 → `Message-ID` 抽出 → 送信側に渡す経路が必要 (個別実装ごとの実機検証は MCP 設定リポの DESIGN.md に記録) |

### スコープに注意

MCP サーバーが取得した OAuth トークンのスコープによって使える API が異なる:

- `gmail.modify`: `batchModify`（ラベル操作・ゴミ箱移動）は可。`batchDelete`（永久削除）は不可
- `mail.google.com`: 全 API が利用可能（フルアクセス）

スコープが足りない場合は GCP コンソールで OAuth 同意画面を更新し再認証が必要。

### 実装時の注意

- Python スクリプトがトークンを refresh した場合、access_token だけでなく **refresh_token も書き戻す**。Google が refresh_token を回転させた場合に旧トークンだけがファイルに残ると、MCP サーバーも Python スクリプトも認証不能になる
- MCP サーバーと Python スクリプトの同時実行は避ける（token refresh の競合リスク）

各ユーザーの具体的な実装（認証情報のパス、スクリプト等）は MCP 設定リポの DESIGN.md に記録すること。

## Google API で create された resource の UI 制約 (third-party tool 制限)

Google API 経由で create された Calendar event / Classroom coursework / Drive file 等の resource は、 Google 側で「third-party tool 由来」 として永続フラグされる場合があり、 **UI 上の一部 toggle / 操作が disable される**ことがある。 これは API ルートで完全に同等な resource を作れないことを意味し、 「UI で create された state を完全再現したい」 use case では UI 経由でしか達成できない。

### 観測された具体例

- **Classroom courseWork**: API 経由で create されたものは `associatedWithDeveloper: true` が永続的に付与され、 UI で「サードパーティ製ツールからの提出は締め切ることができません」 message が表示されて 「期限後に提出を締め切る」 toggle がグレーアウト。 これは creation state (DRAFT / PUBLISHED) を問わず適用、 つまり「DRAFT で API create → UI で toggle flip + publish」 ワークフローでも回避不能 (= API ルート完全 close)。 「生徒はクラスメイトに返信できます」 toggle も同制限の対象と推定 (要 UI 検証、 Google が公開 schema に expose していない UI 専用 toggle 全般が同制限を受ける可能性)
- **Calendar event**: API 経由で create された event は creator の application name が UI に表示される。 一部 advanced settings (recurring rule の細部、 visibility 等) で制限を受ける場合あり (Calendar API は比較的緩い)
- **Drive file**: API 経由で upload された file は「<App name> から作成」 が表示される。 ファイル type 変換 / format 制限が一部働く

### 検出と回避

実装時に判別する手段:
1. **Discovery doc** (`https://<service>.googleapis.com/$discovery/rest?version=v1`) を取得して resource schema 全 field を確認 → UI 上 toggle に対応する field が無ければ **API では set 不可**
2. **Experimental に予想 field 名を投稿** → reject されれば確認 (rare に "silently ignored" もあるので read で echo back されるか確認も)
3. **API で create した resource を UI で開いて toggle / 操作の有効性を確認** → グレーアウト されれば third-party tool 制限あり

回避策:
- UI 完全制御が必要な resource は **UI で create する**経路を残す (= 利用者個別の運用ルールは MCP 設定リポ側の docs / SESSION.md に記録)
- API ルートは**制約を受けても困らない use case** で活用 (e.g., 期限後 late submission を accept する運用、 配点付き ASSIGNMENT、 内部試行 / DRAFT prototype、 batch 投稿)

### 経緯 (本 section 追加の契機)

2026-05-09 Classroom MCP の `classroom_create_coursework` ツール (= `courses.courseWork.create`
を wrap、 SHORT_ANSWER_QUESTION 対応) を実運用に投入する dogfood 段階で、 **API ルートで
「期限後に提出を締め切る」 toggle を ON にできない**ことが判明。 第一段では Discovery
doc + 8 field name experimental 投稿で API field 不存在を確認、 第二段では DRAFT で
create + UI で開く検証で associatedWithDeveloper 永続フラグによる UI grayout も確認
→ API ルート完全 close。 詳細: `gmail-mcp-config/SESSION.md §「2026-05-09
classroom_create_coursework ツール追加 + dogfood 失敗」`、 メタ教訓は
`odakin-prefs/work-discipline.md §広い指示を受けたら... §失敗例 (Classroom
短答課題の自動 publish) §追加発見`。

## Google Calendar MCP
- 操作前にカレンダー一覧で対象カレンダーが正しいことを確認
- 共有カレンダー命名: `{共同研究者名}{自分の名字}共同研究`
- イベント作成時は日時・タイトル・参加者をユーザーに確認してから作成

## Gmail MCP: read_email の大容量出力と chunked 処理

### 現象

`gmail_read_email` / `mcp__gmail-multi__read_email` は HTML-rich なメール（Substack newsletter、他の通知系メール等）で **70〜200 KB の出力**を返す。このサイズは Claude のメインコンテキスト token limit を超えるため、戻り値が error 風のメッセージ + 以下のようなファイルパスになる:

```
Error: result (XX,XXX characters) exceeds maximum allowed tokens.
Output has been saved to /Users/{user}/.claude/projects/{proj-id}/tool-results/mcp-gmail-multi-read_email-{timestamp}.txt
Format: JSON array with schema: [{type: string, text: string}]
```

ファイルには JSON `[{type:"text", text:"..."}]` 形式で、`text` フィールドに email 本文の HTML マルチパート（ときに base64 urlsafe エンコード）が入っている。

### 戦略

1. **メインコンテキストで中身を見たい場合**: 諦める。サイズが常に limit を超える
2. **内容を処理して構造化したい場合**: subagent に委譲。ファイルパスを渡して「Read tool で offset/limit を使って chunk ごとに読み切れ（limit=2000 行推奨）」と**明示する**
3. **複数メールを一括処理したい場合**:
   - メインから `read_email` を**並列で 4〜8 件**発火する
   - 全件 error 応答になるが、error メッセージの中のファイルパスは有効
   - パスのリストを subagent に渡して一括処理させる

### 並列化の注意

- Subagent の**4 並列**起動は 529 Overloaded エラーが頻発する。**3 並列まで**が安全圏
- 失敗した subagent は SendMessage で継続ではなく新規スポーンでリトライする方が確実
- `read_email` 自体の並列（MCP tool call の並列）は 8 件並列まで問題なく動く

### 典型的な処理パターン

```
1. gmail search → message id のリスト取得（メインで完結）
2. メインから read_email を 4-8 件並列発火 → ファイルパスのリスト取得
3. 残りがあれば 2 をもう一度
4. subagent 2-3 本を並列起動、各 subagent に (a) ファイルパスのサブセット
   (b) 抽出ルール (c) 出力先ファイルパス を渡す
5. subagent が各ファイルを Read で chunk ごとに最後まで読み、抽出結果を
   markdown として出力先に Write する
6. メインはファイルパスのみ確認し、必要なら merge
```

### Subagent への指示で忘れやすい点

- **「最後まで読み切れ」と明示する**。default では subagent は最初の chunk だけで判断しがち
- **著作権ガード**: 第三者の著作物（記事本体、他者のコメント本文）を引用しないことを明示する
- **529 時の再試行**: 「少し待ってから再試行」を明示的に指示しないと諦めて終わる
- **完了報告の形式指定**: 「何を抽出できたか (verbatim を除く) を 1 行ずつ報告せよ。要約不要」と書く。書かないと長文要約が返ってきてメインのコンテキストを食う

### Substack 通知メール固有の注意

Substack の `reaction@mg1` / `forum@mg1` 通知メールからユーザーのコメント本文を取得する際の構造的な制約（forum 通知には parent コメントが含まれない等）は → `substack.md` の「取得」セクション参照

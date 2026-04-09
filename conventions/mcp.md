# MCP 規約

MCP ツールを使うリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/mcp.md`

## 共通（CONVENTIONS.md §5.7 の手順詳細）

- **確認方法**: Gmail は `gmail_get_profile`、Calendar は `gcal_list_calendars` で接続先アカウントを確認
- **複数 MCP がある場合**: セッションの deferred tools 一覧で同一サービスの MCP が何個あるか確認し、それぞれ `get_profile` を実行して UUID→アカウントの対応を把握する
- **UUID→アカウント対応表をメモリに保持**: MEMORY.md に `reference_mcp_uuid_map.md` へのポインタがなければ、全 MCP で `get_profile` を実行して作成する。既にあれば deferred tools の UUID 一覧と照合し、差分があれば更新する
- **アカウント一覧の正本**: 各 MCP 設定リポの CLAUDE.md を参照（メモリや各リポの CLAUDE.md にハードコードしない）

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

### スコープに注意

MCP サーバーが取得した OAuth トークンのスコープによって使える API が異なる:

- `gmail.modify`: `batchModify`（ラベル操作・ゴミ箱移動）は可。`batchDelete`（永久削除）は不可
- `mail.google.com`: 全 API が利用可能（フルアクセス）

スコープが足りない場合は GCP コンソールで OAuth 同意画面を更新し再認証が必要。

### 実装時の注意

- Python スクリプトがトークンを refresh した場合、access_token だけでなく **refresh_token も書き戻す**。Google が refresh_token を回転させた場合に旧トークンだけがファイルに残ると、MCP サーバーも Python スクリプトも認証不能になる
- MCP サーバーと Python スクリプトの同時実行は避ける（token refresh の競合リスク）

各ユーザーの具体的な実装（認証情報のパス、スクリプト等）は MCP 設定リポの DESIGN.md に記録すること。

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

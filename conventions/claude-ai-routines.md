# claude.ai routines (= RemoteTrigger API) 規約

claude.ai の **routines** (= かつての「scheduled remote agents」) を扱う際の知識集。 cron expression or one-time trigger で **cloud 側に CCR (Claude Code Remote) session を spawn** する仕組みで、 user の local machine とは独立して動く。

`RemoteTrigger` tool (ToolSearch で `select:RemoteTrigger` で load 可) または `/schedule` skill 経由で操作する。

## 既存 `scheduled-tasks.md` との区別

- **`scheduled-tasks.md`**: Claude Code 内蔵の `create_scheduled_task` / `update_scheduled_task` MCP tool (= SKILL.md ベース、 ローカル Claude バックエンドが prompt を保存)
- **本 file**: claude.ai web 側の `RemoteTrigger` API (= CCR session を cloud で spawn、 cron_expression / run_once_at で trigger)

両者は別 mechanism。 互いに置換不可。 user の意図次第で使い分ける。

## 制約 (= 設計時に必ず考慮)

| 制約 | 意味 |
|---|---|
| **cloud 実行** | remote agent は Anthropic infrastructure 上で動く。 user の `~/Dropbox/`、 `~/Claude/`、 環境変数、 local CLI MCP 等に**一切アクセス不可** |
| **git clone 経由 source 取得** | input data は `job_config.ccr.session_context.sources[]` で git repository URL を指定して clone する形式のみ。 git 経由で取れないもの (= Dropbox / local file / 認証付き API) は agent からは見えない |
| **cron は UTC 解釈** | `cron_expression` は 5-field UTC。 user の local timezone との変換が必要 (= JST → UTC は −9h、 例: 9am JST 毎日 = `0 0 * * *`) |
| **minimum interval = 1 hour** | `*/30 * * * *` 等は reject される。 5 分刻みの polling 等は別 mechanism (= GitHub Actions cron 等) を選ぶ |
| **run_once_at は未来 UTC** | one-time trigger は `YYYY-MM-DDTHH:MM:SSZ` RFC3339 UTC、 過去なら reject。 user の相対表現 (= 「明日 9 時」) は `date -u` で fresh time を取得してから resolve |
| **routine 削除は API 不可** | `RemoteTrigger` action に `delete` なし。 user に <https://claude.ai/code/routines> へ誘導 |

## 推奨設計 pattern

### Hybrid notify pattern (= local-required workflow との橋渡し)

remote agent は local file に触れないため、 local 完結の workflow (= 例: `~/Dropbox/` の roster sync、 user の handwritten note 反映) を全自動化できない。 解決 pattern:

- **remote agent の仕事**: source repo に **reminder file を commit + push** (= 例: `reminders/YYYY-MM-DD-<task>.md`)
- **通知経路**: GitHub の commit-on-push email、 または user の dashboard で reminder file の存在を surface
- **実 sync**: user が手元 Mac で reminder の指示に従って手動実行

これは「remote agent の出力 = git commit」 という設計で、 cloud と local を非同期に bridge する。

### Prompt は self-contained

remote agent は zero context で起動する (= 前回 session の memory なし、 user の chat 履歴なし、 私の作業状態なし)。 prompt に以下を必ず含める:

- 「今日は何月何日 (= 4/1 or 8/1 等の trigger 日付)」 という anchor
- 背景 (= なぜ起動されたか、 何を達成すべきか)
- 詳細 plan file への path (= source repo に同梱、 例: `~/Claude/<repo>/plans/<plan>.md`)
- 完了 message として何を出力すべきか (= GitHub URL、 file path 等)
- **触らない範囲**の明示 (= 例: 「他リポは触らない」)

### MCP connectors の auto-attach

routine create 時、 `mcp_connections` を body に指定しなくても、 user の claude.ai connector 設定 (= Google_Calendar / Gmail 等) が**自動 attach される**。 prompt で使わないなら ignore で OK だが、 副作用 (= 意図しない calendar 操作) のリスクを認識。 minimize したい場合は routine create 後に web UI で disconnect。

### allowed_tools 最小化

`session_context.allowed_tools` で agent が使える tool を絞る。 reminder file 作成だけなら:

```json
"allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
```

= file 操作 + git command (= Bash) のみ。 Network fetch / WebSearch 不要なら除外。

## RemoteTrigger API quick reference

| action | 用途 | required |
|---|---|---|
| `list` | 全 routine 一覧 | (なし) |
| `get` | 単一 routine 取得 | `trigger_id` |
| `create` | 新規作成 | `body` (= name + cron/run_once + job_config) |
| `update` | 部分更新 | `trigger_id` + `body` |
| `run` | 即時実行 (= test 用) | `trigger_id` |

create body の minimal shape:

```json
{
  "name": "<descriptive name>",
  "cron_expression": "<5-field UTC>",
  "enabled": true,
  "job_config": {
    "ccr": {
      "environment_id": "<env_id>",
      "session_context": {
        "model": "claude-sonnet-4-6",
        "sources": [{"git_repository": {"url": "https://github.com/<org>/<repo>"}}],
        "allowed_tools": ["Bash", "Read", "Write", "Edit"]
      },
      "events": [{
        "data": {
          "uuid": "<fresh lowercase v4 uuid>",
          "session_id": "",
          "type": "user",
          "parent_tool_use_id": null,
          "message": {"content": "<self-contained prompt>", "role": "user"}
        }
      }]
    }
  }
}
```

one-time の場合は `cron_expression` を `run_once_at` (= RFC3339 UTC) に置換。

## 反パターン

- **local 完結 workflow を remote agent で全自動化を試みる** (= cloud で local file に触れないため必ず失敗する)。 hybrid pattern (= reminder のみ remote + 実 sync は local) に divert する
- **cron expression を JST で書く** (= UTC に変換せず `0 9 1 4 *` を「毎年 4/1 09:00 JST」 と意図 → 実際は毎年 4/1 09:00 UTC = JST 18:00 で発火、 9h ずれ)
- **prompt を「先回 session の続き」 と書く** (= remote agent は zero context、 必ず stand-alone に書く)
- **`scheduled-tasks.md` の SKILL.md 同期 ルールを本 routine に適用** (= SKILL.md は別 mechanism で、 本 routine の prompt は API response 内に保存される。 git 同期 task 不要)

## 過去事例

- **2026-05-21 odakin の zemi-roster-sync routine**: schedule skill を「マシン依存しない ◎」 と reflex 評価 → skill 内容を確認したら「cloud 実行 = local file 触れない」 と判明 → hybrid pattern (= reminder file commit + local 手動 sync) に redesign。 詳細 RCA は `odakin-prefs/work-discipline.md §「単一情報源 null 結論飛躍」 事例 #4`

## 関連 doc

- `~/Claude/claude-config/conventions/scheduled-tasks.md` — 旧 mechanism (= Claude Code 内蔵 scheduled task)、 本 file とは別 system
- `~/Claude/claude-config/conventions/multi-session-coordination.md` — cross-session 一般則
- `~/Claude/claude-config/conventions/mcp.md` — MCP / connectors 全般

## 由来

2026-05-21 セッションで odakin が物理研究室メンバー名簿の sync 自動化を `schedule` skill で実装した際、 skill 内容を確認せず「マシン依存しない」 と reflex 評価 → 制約発覚で redesign → 一般則を本 file に集約。

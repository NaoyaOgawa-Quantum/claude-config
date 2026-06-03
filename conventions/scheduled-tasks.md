# Scheduled Tasks 規約

Claude Code scheduled tasks を使うリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/scheduled-tasks.md`

## 0. 実行 locus で機構を選ぶ (= scheduled task が正しい道具か先に問う)

定期/自動ジョブを組む前に、 **(1) run-time に Claude の judgment が要るか** + **(2) 何にアクセスするか** で実行機構を選ぶ。 「定期 = scheduled task」 と reflex で選ぶと、 deterministic job に Claude を毎回起こす過剰や、 cloud routine の local-access 不在に後で衝突する。

| ジョブの要件 | 機構 | 理由 |
|---|---|---|
| **deterministic** な機械処理 (= run-time に Claude judgment 不要) で local file/repo/CLI (sips, npm, git push) に依存 | **launchd / cron (該当マシンで local 実行)** | local 実行・token cost ゼロ・LLM 非依存・Claude runtime 不要。 純粋な script はこれが最適 |
| **Claude の judgment / draft** が run-time に要る (+ PushNotification を使いたい) | **Claude Code scheduled task (SKILL.md)** | **local の fresh Claude session で実行され local file/cred に アクセスできる** (= 実例: daily-mail-triage-check が `~/Claude/.../*.py` を local OAuth `~/.gmail-mcp/` で実行)。 「backend」 は **prompt の保存先**であって実行 locus ではない (下記 §アーキテクチャ) |
| 職場/組織 NW から API が block される (例: campus から Discord API が Cloudflare 1010) | **GitHub Actions (cloud cron)** | 別 network egress から実行 + secret で credential 供給 |

⚠️ **`schedule` skill の「remote agent / routine」 は上記 scheduled task とは別物**: これは **cloud で起動し local file に一切アクセスできない** (= 過去に「local 完結 script を schedule skill で trigger」 が cloud 実行で根本的に動かず redesign した RCA)。 local 依存ジョブを cloud routine に載せない。 **scheduled task (= local) と混同しない** (= 「scheduled task は local 不可」 は誤り、 上記の通り local access あり)。

**reflex**: 「定期実行 = scheduled task」 ではない。 まず **(1) run-time に Claude judgment が要るか** — 不要 (= 純粋 script) なら launchd/cron (= Claude を毎回起こさない、 決定的、 無料)。 要るなら scheduled task (= local access あり)。 次に **(2) cloud に出す必要があるか** — NW block 回避なら GitHub Actions、 それ以外で local 依存があるなら cloud routine (schedule skill) を避ける。 実行 locus が不確かな機構は、 local access を前提にする前に locus を検証する (= 機構名から「remote だろう」 と推測せず実証する)。

machine-local job を「どのマシンに登録するか / 登録漏れをどう surface するか」 は [multi-machine-state.md](multi-machine-state.md)。 無人 publish の安全 gate は [data-pipeline-automation.md](data-pipeline-automation.md) §7。

## アーキテクチャ: SKILL.md とバックエンドの二重構造

### 構造

```
リポ/skill/{task-id}/SKILL.md     ← git 管理（差分追跡・レビュー用）
        ↑ symlink
~/.claude/scheduled-tasks/{task-id}/SKILL.md  ← ローカル参照
        ✗ 実行時には読まれない

Claude バックエンド（リモート）    ← 実際に実行される prompt
```

### なぜこうなっているか

- **SKILL.md をリポに置く理由**: git で差分追跡・コードレビューができる。複数端末間で `git pull` で内容を共有できる
- **バックエンドが SKILL.md を読まない理由**: scheduled task の実行 prompt は `create_scheduled_task` / `update_scheduled_task` 呼び出し時にバックエンドに保存され、以後ローカルファイルは参照されない（Claude Code の仕様）
- **symlink の役割**: ローカルで `~/.claude/scheduled-tasks/` を見たとき、SKILL.md の内容をリポ側で一元管理するための便宜。実行には影響しない
- **「バックエンド（リモート）」 の正確な意味**: これは **prompt の保存先**を指す (= prompt 本文が backend に保存される)。 **agent の実行自体は該当マシンの local fresh session** で、 **local file / OAuth token / CLI に access できる** (= 実例: daily-mail-triage-check の SKILL.md は `~/Claude/.../*.py` を local OAuth `~/.gmail-mcp/` で実行する前提で書かれ、 §15 メール防御の一部として依存されている)。 ⚠️ 「backend remote 保存」 を「remote 実行 = local file 不可」 と誤読しないこと (= §0 の機構選択で「scheduled task は local 不可」 と誤判定する原因になる)。 cloud で実行され local file に触れないのは別物の **`schedule` skill の routine** の方 (§0 参照)

### 制約

SKILL.md を single source of truth にできない。リポの SKILL.md とバックエンドの prompt が乖離するリスクが常にある。

## ルール

### SKILL.md にステップ0: SESSION.md チェックを含める（必須）

Scheduled task のエージェントは CLAUDE.md / CONVENTIONS.md を確実に読む保証がない。そのため SESSION.md の要対応事項が無視されるリスクがある。対策として、**各 SKILL.md の冒頭にステップ0として SESSION.md チェックを明記する**。これは CONVENTIONS.md §3 の「リポでの作業開始手順」を task prompt 内で確実に発火させるためのもの。

CONVENTIONS.md のルール（人間セッション・手動実行をカバー）と SKILL.md のステップ0（scheduled task 自動実行をカバー）は役割が異なり、両方必要。

### SKILL.md 編集時（必須）

1. リポの SKILL.md を編集する
2. **直後に `update_scheduled_task` で prompt フィールドを同期する**
3. コミット・push する

この順序を守らないと、バックエンドが古い prompt のまま実行される。

### 新規タスク作成時

1. `create_scheduled_task` でバックエンドに登録（prompt を渡す）
2. リポに `skill/{task-id}/SKILL.md` を作成（同じ内容）
3. symlink を張る: `ln -s /path/to/repo/skill/{task-id}/SKILL.md ~/.claude/scheduled-tasks/{task-id}/SKILL.md`

### マルチマシン運用

- バックエンドはマシンごとに独立。マシン A で `update_scheduled_task` しても、マシン B のバックエンドは更新されない
- 新しいマシンで pull 後、そのマシンで使う scheduled task は `update_scheduled_task` で prompt を同期すること
- SESSION.md にマシン固有の要対応事項を書いておくと pull 後に気づける

## パス表記について

本ドキュメントおよび各リポの CLAUDE.md では `~/Claude/` をハードコードしている。これは現運用者（odakin）の全マシンで統一されたパスであり、`<base>` のような抽象化は行わない。共同編集者が `~/github/` 等の別パスを使っていても、本規約はリポオーナーの Claude Code scheduled task 運用にのみ適用されるため問題ない。共同編集者が scheduled task を運用する場合は、その時点でパス抽象化を検討する。

## 経緯

- 2026-03 symlink 方式を導入。SKILL.md 編集が自動反映されると想定していた
- 2026-04-01 `inspire-monthly` で同期漏れが発覚。バックエンドが旧 prompt で実行され、存在しないモジュール `arxiv_digest.profile` を呼んで失敗
- 原因調査の結果、バックエンドは SKILL.md を実行時に読まないことが判明。手動同期ルールを導入

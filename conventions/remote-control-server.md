# Remote Control サーバーモードの launchd 常駐 (= スマホからいつでも Claude Code)

`claude remote-control` (サーバーモード) は、スマホの Claude アプリや claude.ai/code から
**自分のマシン上に新規 Claude Code セッションを生やせる待ち受けサーバー**。実行は常に
ローカルマシン側なので、filesystem・MCP・hooks・settings がそのまま使える (= Anthropic
インフラで動く cloud session とは別物)。これを launchd で常駐させると「常時起動マシンが
ある人は、いつでもどこでもスマホから自分の環境で Claude Code」になる。

install / plist / KeepAlive 設計の SoT は `scripts/install-remote-control-server.sh`
(= 本 doc は要件・落とし穴・運用知見のみ。公式 doc: https://code.claude.com/docs/en/remote-control)。

## 使い方

```sh
# 常時起動しているマシンで 1 回 (idempotent)。--dir がリモート生成セッションの root
sh scripts/install-remote-control-server.sh --dir "$HOME/my-projects"

sh scripts/install-remote-control-server.sh --status      # 稼働確認 + log tail
sh scripts/install-remote-control-server.sh --uninstall   # 解除
```

接続側: スマホ Claude アプリ → Code タブ (またはブラウザで claude.ai/code) →
**緑ドット + computer icon** の environment を選んで新規セッション作成。

## 要件 (= 欠けていても install は通り、解消後 60 秒以内に自動で生き返る)

| 要件 | 欠けた時の症状 | 解消 |
|---|---|---|
| macOS + Claude Code v2.1.51+ | — | `claude update` |
| **claude.ai OAuth login** (subscription 必須) | log に「must be logged in」で即 exit を繰り返す | ターミナルで `claude auth login`。⚠️ API key・旧「managed key」型の credential は不可 — `claude auth status` が loggedIn でも `subscriptionType: null` ならこれ (2026-06-12 実測) |
| **初回同意** (一度だけ) | log に「Enable Remote Control? (y/n)」、無人では進めない | ターミナルで `claude remote-control` を一度起動して y (= `~/.claude.json` の `remoteDialogSeen` に永続化) |

## 設計の要点 (= 変更・移植する人向け)

- **復元力**: `KeepAlive` + `ThrottleInterval 60` で 再起動 / crash / 未認証 / ネットワーク断
  (10 分超で claude 側が自滅する仕様) の全てから自動復帰。放置運用前提。
- ⚠️ **PTY を与えてはいけない**: launchd 配下で script(1) 等の PTY 経由にすると、stdin
  (/dev/null) の EOF が端末 close として claude に届き graceful exit → 60 秒周期の
  接続/切断 cycling になる (2026-06-12 実測 RCA)。non-TTY 直接 exec なら stdin EOF を
  無視して安定する (= TUI の QR 表示等は失うが、サーバー機能に不要)。
- shutdown 時の「Environment preserved」は正常 (= environment は再起動を跨いで維持され、
  同じ environment ID で再接続する)。

## 運用知見 (実測)

- **モバイル UI の「リポ選択」は cwd を変えない**: 既定の `--spawn same-dir` では新規
  セッションの cwd は常にサーバーの `--dir`。UI で何を選んでも変わらない (2026-06-12
  transcript 配置で実測)。リポ単位で隔離したければ `--spawn worktree` (= `--dir` 自体が
  git repo である必要、セッション毎に worktree)。
- **cloud session との取り違え注意**: アプリの新規作成 UI には「ローカル (Remote Control)」
  と「cloud session (Anthropic インフラ、GitHub repo 必須)」が同居する。緑ドット +
  computer icon がローカル。
- **死んだセッションの残骸**: サーバー再起動を跨ぐと旧セッション行が一覧に残り、開くと
  無限スピナーになる。残骸は削除し、新規作成で入り直す。
- 並列セッションは同じ cwd を共有する (same-dir) ので、同一ファイルの同時編集は衝突し得る。

## セキュリティ

- 通信は**外向き HTTPS のみ** (Anthropic API 経由の polling)。inbound port は開かないので
  NAT / FW 配下でも動き、露出面の追加はほぼ無い。
- リモート生成セッションは通常のローカルセッションと同じ settings.json / hooks /
  permission mode に従う (= permission の絞りは settings 側で行う。
  `claude remote-control --permission-mode <mode>` で spawn 時の mode 指定も可)。
- スマホを持つ人 = あなたのマシンで Claude Code を動かせる人。端末ロックは前提。

## 相補機能

- `remoteControlAtStartup: true` (`~/.claude/settings.json`、machine-local): 手元で開いた
  **対話セッション全部**を自動でリモート続行可能にする。サーバーモード (= 何も開いて
  いなくても外から新規に生やす) とは役割が別で、併用が自然。

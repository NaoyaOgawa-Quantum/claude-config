# multi-machine-state: 複数マシンで同じ Claude Code セットアップを使うときの規律

複数マシン (家・職場、ノート・デスクトップ等) で同じ `~/Claude/` (または等価な base dir) を運用する場合、**マシンごとに state が drift する** 前提で設計・記録・audit する。

## State の分類: 何が同期され、何がしないか

| 種類 | 例 | 同期手段 |
|---|---|---|
| Repo content | 各 repo の commit 内容 | `git pull` (repo ごと) |
| 共通設定 | `~/.gitignore_global` / Claude Code hooks / CONVENTIONS.md symlink | `claude-config/setup.sh` Step 6 の post-merge hook で claude-config pull 後に自動同期 |
| マシンローカル state | `~/.claude.json` (MCP 登録) / OAuth tokens / アプリの Local Storage 等 | **同期されない**。マシンごとに独立。各 repo の冪等な `setup.sh` を再走して揃える |

「同期されない」カテゴリの存在を意識しないと、片方のマシンで commit した doc 変更が反映されても、ローカル state は古いまま、という drift が静かに広がる。

## Audit 結論には scope を明示する

「実態を再検証した」「全件確認した」と書く audit セッションは、**観察したマシン (どの machine で実行したか) と観察した時刻** を結論文に明記する。書き忘れると、別マシン上の Claude が結論を canonical と誤読し、別マシンの state を上書きしてしまう。

NG:

> 監査の結果、X は不在で、Y パッケージは一度も install されていなかった。

OK:

> [<machine-A> 上で <date> に実行した] 監査の結果、本マシンでは X は不在で、Y パッケージはこのマシンでは install されていなかった。他マシンの state は別途検証が必要。

audit を実行するマシン名は事後の commit message にも書いておくと、後で git log を遡る時に scope を取り違えない。

## 「実装は走らなかった」「patch は no-op だった」型の断定は実機検証してから書く

Audit narrative で **implementation reality を否定する断定** (「実装されていない」「target file が存在しないので空打ち」「該当箇所は走らなかった」等) は、narrative 推論ではなく `ls` + `stat` (mtime / size) / 実機ファイル内容で確認してから書く。「推定」とコメントを添える時点で、推定対象の実機検証を踏むコストは ls 1 回分しかない — 必ず踏む。

narrative 推測のまま canonical doc に書くと、別マシン上で覆る (= drift) 可能性が高く、結果として「過去の自分が書いた audit 結論」と「今の実機状態」がループ的に矛盾する状況に陥る。

## マシン間 drift の reconciliation 経路: idempotent setup.sh

State drift が起きうる箇所 (= 上の「マシンローカル state」) では、**idempotent な `setup.sh` を canonical reproducer として用意**する。各マシンで再走すれば差分だけ埋まる、という経路を確保しておく。

冪等化のキー:

- **既存 state を検出して skip**: 例として、トークンが既に配置されているならコピーと OAuth フローを skip。「上書きしてからやり直し」ではなく「足りないものだけ補う」を default にする
- **旧 state を検出して migrate**: 古いパッケージ登録を `remove` してから新パッケージを `add`、のような「state machine の遷移」を script に閉じ込める
- **target を引数 / 環境変数で明示できるようにする**: cwd 依存にしない (cf. 同ディレクトリの [`mcp.md`](mcp.md) §`claude mcp` の project 解決ルール)。スクリプト冒頭で `cd "$TARGET"` する形にして、cwd 暗黙依存をなくす

これが揃うと、drift 検出時の reconciliation はマシンごとに `setup.sh` を再走するだけで完了する。再走が destructive (token を破壊する等) だと「念のため再走」をしづらく、drift の発見も遅れる — 冪等性は drift 検出の前提条件でもある。

## 関連

- 同じ system に対する別マシンの観察結果を比較する経路は、各 repo の `DESIGN.md` に「<date> の machine-X observation」の節を立て、別マシンでの観察を追記する形で蓄積するのが追跡しやすい (「audit を上書きする」のではなく「audit に scope qualifier と別マシン観察を追加する」アプローチ)
- マシン横断の repo pull 経路は各ユーザーの個人レイヤーで決める (例: 個人スクリプト `pull-all.sh` を持つ等) — 本リポ public 共通規約には組み込まない

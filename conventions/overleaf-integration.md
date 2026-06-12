# Overleaf <-> GitHub Integration

複数 author で論文を書くとき (= 共著者 1 人以上、 Overleaf project + GitHub repo を併用) の同期経路。

## TL;DR

**Canonical = Overleaf project の web UI で設定する GitHub linking**。 user が Overleaf web で "Pull GitHub changes into Overleaf" / "Push Overleaf changes to GitHub" ボタン 1 つで bidirectional sync 可能 (= linking active 中は user 操作で生成された commit が自動 propagate)。

**Secondary = local mirror clone (`.overleaf-mirror/`)**。 共著者等の共著者が Overleaf で編集中の最新状態を local で `diff -r` 確認したい用途のみ。 **mirror から直接 git push は禁止** (= GitHub linking と競合して 403 timeout)。

⚠️ **Overleaf が正本の repo では、 GitHub/local の `git pull` が "Already up to date" でも Overleaf 最新とは限らない** (= 三例目で 3 ヶ月 drift)。 連携形態を問わず **`scripts/overleaf-sync.sh` を必ず整備** (= project ID の SoT + `--status` drift probe、 §Sync script 契約)。

## 推奨 setup 手順

1. Overleaf project を user が作成 (= `overleaf.com`)
2. paper repo を GitHub に作成 (= `odakin/<paper-name>` 等、 paper の真の master)
3. user が Overleaf web で **Menu → Sync → GitHub → Link with a GitHub repository** をクリック、 GitHub repo を選択 + collaborator 設定
4. linking 完了後、 Overleaf web の Sync メニューに "Pull GitHub changes into Overleaf" / "Push Overleaf changes to GitHub" ボタン出現
5. (任意) local read-only mirror を追加:
   ```bash
   OVERLEAF_TOKEN=$(tr -d '\n' < ~/.secrets/overleaf-token)
   cd <repo_root>
   git clone "https://git:${OVERLEAF_TOKEN}@git.overleaf.com/<project_id>" .overleaf-mirror
   unset OVERLEAF_TOKEN
   echo ".overleaf-mirror/" >> .gitignore   # mirror を main repo から隔離
   ```

## Sync 経路の使い分け

| 場面 | 操作 |
|---|---|
| Local / GitHub main 更新 → Overleaf に反映 | user が Overleaf web で **"Pull GitHub changes into Overleaf"** クリック |
| 共著者の Overleaf 編集 → GitHub に反映 | 通常は **auto-sync** (= linking active で自動)、 もしくは user が "Push Overleaf changes to GitHub" クリック |
| 共著者が Overleaf で編集中の最新状態を Claude が確認 | `cd .overleaf-mirror && git pull` で取得 → `diff -r` で本文と比較 |
| Local edit を Overleaf に流す | (1) local で commit + push to GitHub main、 (2) user が Overleaf web で "Pull GitHub changes into Overleaf" |

## bidirectional auto-sync の挙動

linking active 中、 user の Overleaf web 操作で生成された commit は **自動的に GitHub にも push 戻る**。 例えば:
- user が "Pull GitHub changes into Overleaf" クリック → Overleaf に merge commit (= 例: `78e8cc6`) → 自動的に GitHub にも push (= `Updates from Overleaf` + `Merge overleaf-... into main` の 2 commits)
- 結果: 同じ content だが commit hash が異なる版が両 remote に存在 (= bookkeeping commits)

paper の content は不変、 commit graph が複雑化する程度。 local main を update する側は **pull → push** の merge 流儀になる。

## ⚠️ mirror 経由の直接 push 禁止

mirror clone (= `.overleaf-mirror/`) から `git push origin master` しようとすると **403 timeout**:
- 元の push: Overleaf server で 360 秒以上応答なし → reject
- retry: GitHub linking との競合で 403

対処: **mirror から直接 push しない、 GitHub linking 経由で auto-sync**。

mirror script (= sync-overleaf.sh template) を作る場合は、 冒頭 comment で「逆方向 push は動作しない」 warning を明示。

## Token 管理

Overleaf personal access token (= `olp_*` で始まる ~40 char):
- 取得: Overleaf web の **Account Settings → Git Integration → Generate token**
- 保管: `~/.secrets/overleaf-token` (= mode 600)
- Dropbox encrypted backup の方針は odakin の case で `secrets-config/CLAUDE.md §Overleaf` 参照

token は account 単位、 project access 権限とは別 layer。 token 期限切れと collaborator 権限 deny を切り分ける手順:
- fetch + push 両方 403 + 新 token でも 403 → permission/timing issue (= token は関係ない)
- 元の push が timeout → Overleaf 側の server 状態 (= rate limit、 GitHub linking 競合)

## 変種: direct remote + 手動 merge (GitHub repo 併用、 GitHub linking 無し)

Overleaf project と GitHub repo を併用するが GitHub linking を張らない場合。 共著者は
Overleaf を直接編集し、 owner が overleaf remote から fetch + merge して GitHub 側へ
取り込む (= `git fetch "https://git:<token>@git.overleaf.com/<project_id>" "+master:refs/remotes/overleaf/master"` →
`git merge overleaf/master`。 URL 直指定 fetch なら token が `.git/config` に永続化しない)。

- merge conflict をどちら側採用で解決するか (通常 = 正本である Overleaf 側) を repo に明記
- ⚠️ **この変種は「GitHub pull = 最新」 という錯覚が最も起きやすい** (= 下記 三例目)。
  GitHub に届くのは「誰かがどこかのマシンで merge した時点」 までで、 以降の Overleaf
  編集は **どの clone の `git pull` にも現れない**。 Overleaf が正本の repo では
  up-to-date 判定は overleaf remote への fetch でしか確定しない
- merge は特定マシンの clone で行われがち = その clone が消えると remote 設定ごと
  project ID も消える (= 三例目の ID 喪失経路)。 下記 §Sync script 契約 が必須

## Sync script 契約 (= 全変種共通の標準、 三例目 2026-06-12 で標準化)

Overleaf 連携 repo には **`scripts/overleaf-sync.sh` を必ず置く** (= 連携を張った
session 内で作る。 「あとで整備」 は ID 喪失の前兆):

- **PROJECT_ID を script 冒頭に hardcode して commit** = ID の single source of truth
  (= 一例目 / 二例目 / 三例目すべて ID の置き場所が原因系)。 ID 未確定でも placeholder
  (例 `FIXME_PROJECT_ID`) で script を先に commit し、 script は exit 2 で拒否する
  (= drift 検出器が「ID 未設定」 を surface し続け、 忘却で消えない)
- **`--status` mode**: read-only probe。 fetch して `ahead=N behind=M` を 1 行出力
  (= 機械可読契約、 behind>0 = Overleaf に未取込みの共著者編集)。 設定不足
  (token 無し / ID placeholder) は exit 2
- token は `~/.secrets/overleaf-token` から読み、 出力は `olp_…` を自動マスク
  (上記 §Token 管理)
- 連携を廃止したら script を削除せず **冒頭で `DEPRECATED` を表示して exit 0** に
  置換する (= 検出器が「廃止済」 と機械判別でき、 既存 hook も壊れない)
- Overleaf への push は共著者の編集環境に直接影響 → script で自動化しない、
  user 明示確認必須
- repo の CLAUDE.md に同期 mode (= GitHub linking / direct remote + 手動 merge /
  direct nested clone のどれか) + merge conflict 方針を明記

**drift 監視**: 横断 dashboard / cron から各 repo の `--status` を並列実行し、
behind>0 / ID 未設定 / 未 bootstrap / 「Overleaf 連携の記述があるのに script 未整備」
を surface する (odakin の case: 個人層 `check-overleaf-drift.py` を
unified-dashboard 末尾に統合)。

## 変種: direct nested clone (Overleaf = 唯一の source、 GitHub linking 無し)

共著者が Overleaf でノートを書き、 GitHub linking を張らない / 張れない場合 (= Overleaf project がそのまま唯一の正本、 GitHub repo を介さない)、 paper repo 内に **gitignore 除外のローカル専用入れ子 clone** を置いて read 方向で取り込む。 上の GitHub linking 経路とは別物 (= こちらは master が Overleaf 側、 push は共著者に直接影響するので user 明示 OK 必須)。

設計:
- 配置: `<repo>/external/overleaf/` (`.gitignore` に `external/` を入れて本体から隔離)
- token: `~/.secrets/overleaf-token` (= 上記 §Token 管理と同じ。 clone URL `https://git:$(cat ~/.secrets/overleaf-token)@git.overleaf.com/<project_id>` にのみ埋め込み、 出力は `olp_…` を必ずマスク)
- **project ID は paper repo 側 (= layer 2) に記録する**。 ⚠️ ID を gitignore 除外の clone 内 (`external/overleaf/.git/config`) だけに置くと、 **別マシン / clone 削除で完全な ID が失われ**、 他マシンや Overleaf web から手で回収する羽目になる (= 2026-06-08 に実際発生。 同期されていたのは ID 先頭 8 桁の truncation だけだった)。 対策 = **冪等 bootstrap script に PROJECT_ID をハードコードして commit** し、 script を ID の single source of truth にする。
- 冪等 bootstrap script (= 無ければ clone / あれば `git pull --ff-only` / token 無ければ `restore-secrets.sh` 案内) を repo 内に置き、 **新マシン手順を「repo clone → restore-secrets (一度) → sync script」 の 1 直線**にする。

⚠️ layer 注意: project ID は**その paper repo (layer 2) に置く**のが正しい。 layer 1 (本 repo = public) に individual project の ID を書かない (= 公開リポ衛生 + 規約は汎用知識のみ)。 layer 3 (個人層) に置くと layer 2 の script が layer 3 を参照する依存違反になる (= collaborator は個人層を読めない)。 自己完結する layer 2 が audience-correct な最上層。

## なぜこの設計が optimal か

- **bidirectional auto-sync**: linking active 中、 commit が自動 propagate
- **数式変更安全弁**: user が "Pull" を明示操作するまで Overleaf 側は変わらない (= GitHub auto-push を Overleaf 側で reviewable)
- **conflict 回避**: 私 (Claude) が mirror から直接 push しようとすると linking と競合 → 403 で fail-safe (= 経路を間違うと自動的に reject される)

## Claude への規律

設計判断で「既存サービスの built-in 機能は困難 / 不可能」 と assertion する前に、 user の web UI を確認するか user に「サービスに X 機能ないか?」 と聞く。 文献的推測 (= service capability の cell 埋め) で却下すると、 後で built-in 機能が存在することが判明して設計やり直しになる (= ある private paper repo で 1 度発生)。

これは CLAUDE.md inline §13 trait family (= 安価な操作で expensive な操作を bypass する) の現れ。 設計の reasoning domain でも同じ trait が出る。

## 実例

ある private paper repo (2026-05-19) で発見 + 経路改訂。 詳細経緯 + 全 4 拠点 (GitHub main / Overleaf master / mirror / local working tree) の同期確認: `(該当 private paper repo の DESIGN.md)`。

## 実例と refine 履歴 (新例が出たら本 convention を refine)

- 一例目 (2026-05-19): ある private paper repo で GitHub linking + mirror 経路を確立。
- 二例目 (2026-06-08): 別の物理共著 note repo で **direct nested clone 変種** (= Overleaf が唯一の source、 GitHub linking 無し) が発生 → 上の §「変種: direct nested clone」 を新設。 ID を gitignore 除外 clone 内だけに置いて失われた RCA を反映。
- 三例目 (2026-06-12): 別の物理共著 paper repo で **direct remote + 手動 merge 変種**の二重事故が発覚。 (a) 過去の merge を実施した clone が消えて **project ID の記録がゼロ** (= 二例目と同型の ID 喪失が、 規約制定後に別 repo で再発 — 規約は「nested clone 変種」 の文脈でしか書かれておらず、 既存 repo への横断適用 sweep がなかった)。 (b) **3 ヶ月間 Overleaf drift が未検出** = user も Claude も「GitHub pull = Already up to date」 を「最新」 と誤読する構造 (= 検証手段そのものが存在しなかった)。 → §「変種: direct remote + 手動 merge」 + §「Sync script 契約」 を新設し、 script 必須化 + `--status` 機械可読契約 + 横断 drift 監視を標準化。 教訓: **連携形態が 1 つ増えるたびに「ID はどこに記録されるか」「drift は誰が検出するか」 の 2 問を通す**。

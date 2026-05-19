# Overleaf <-> GitHub Integration

複数 author で論文を書くとき (= 共著者 1 人以上、 Overleaf project + GitHub repo を併用) の同期経路。

## TL;DR

**Canonical = Overleaf project の web UI で設定する GitHub linking**。 user が Overleaf web で "Pull GitHub changes into Overleaf" / "Push Overleaf changes to GitHub" ボタン 1 つで bidirectional sync 可能 (= linking active 中は user 操作で生成された commit が自動 propagate)。

**Secondary = local mirror clone (`.overleaf-mirror/`)**。 安田くん等の共著者が Overleaf で編集中の最新状態を local で `diff -r` 確認したい用途のみ。 **mirror から直接 git push は禁止** (= GitHub linking と競合して 403 timeout)。

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
| 安田くんの Overleaf 編集 → GitHub に反映 | 通常は **auto-sync** (= linking active で自動)、 もしくは user が "Push Overleaf changes to GitHub" クリック |
| 安田くんが Overleaf で編集中の最新状態を Claude が確認 | `cd .overleaf-mirror && git pull` で取得 → `diff -r` で本文と比較 |
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

## なぜこの設計が optimal か

- **bidirectional auto-sync**: linking active 中、 commit が自動 propagate
- **数式変更安全弁**: user が "Pull" を明示操作するまで Overleaf 側は変わらない (= GitHub auto-push を Overleaf 側で reviewable)
- **conflict 回避**: 私 (Claude) が mirror から直接 push しようとすると linking と競合 → 403 で fail-safe (= 経路を間違うと自動的に reject される)

## Claude への規律

設計判断で「既存サービスの built-in 機能は困難 / 不可能」 と assertion する前に、 user の web UI を確認するか user に「サービスに X 機能ないか?」 と聞く。 文献的推測 (= service capability の cell 埋め) で却下すると、 後で built-in 機能が存在することが判明して設計やり直しになる (= ejp-revision で 1 度発生)。

これは CLAUDE.md inline §13 trait family (= 安価な操作で expensive な操作を bypass する) の現れ。 設計の reasoning domain でも同じ trait が出る。

## 実例

ejp-revision (2026-05-19) で発見 + 経路改訂。 詳細経緯 + 全 4 拠点 (GitHub main / Overleaf master / mirror / local working tree) の同期確認: `ejp-revision/DESIGN.md §7.7`。

## 二例目が出たら refine

将来 time-energy-head-on (Oda + Ogawa) や twcu-phys-* で同様の Overleaf 共著が発生したら、 本 convention を refine。 現状は ejp-revision で完結。

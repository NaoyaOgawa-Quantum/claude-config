# 共有リポ規約 — Shared Project Layer

共同編集者がいるリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/shared-repo.md`

このファイルは Claude Code 4 層モデルの **layer 2（共有プロジェクト層）** の規約。詳しい層モデルは [`docs/personal-layer.md`](../docs/personal-layer.md) を参照。

## Git workflow（必須）

### セッション開始時
「作業開始」「スタート」等の合図があったら:
1. `git status` で状態チェック
   - **未コミット変更あり** → 「前回の変更が未 commit です。先に commit & push しますか？」
   - **未 push コミットあり** → 「前回の commit が未 push です。先に push しますか？」
2. `git pull` でリモートと同期（コンフリクト発生時はユーザーと解決）
3. **他所からの open PR を確認**: `gh pr list --search "-author:@me"` で自分以外が著者の open PR を一覧。0 件なら次へ。1 件以上ならタイトル・著者・更新日を提示し、「先にレビューしますか？それとも今のタスクを進めますか？」とユーザーに判断を仰ぐ。レビュー先行を選ばれたら `gh pr view <num>` / `gh pr diff <num>` で内容を確認し、所見を提示する。
   - **判断材料**: PR が触るファイルと今のタスクの重なり（競合可能性）、CI 失敗・reviewer unblock 待ちの緊急度
4. リマインダー表示: **「作業が終わったら commit & push を忘れずに！」**

### セッション終了時
「おわり」「終了」「今日はここまで」等の合図、またはお礼・挨拶があったら:
- `git status` を実行し、未コミット/未 push があればリマインドする
- クリーンなら「変更なし。お疲れさまでした。」

## .gitignore

共同編集者が `~/.gitignore_global` を設定しているとは限らない。共有リポでは `.gitignore` に全パターンを明記する:
```
.DS_Store
*~
*.swp
*.swo
```
LaTeX リポの場合は [conventions/latex.md](latex.md) の .gitignore セクションも参照。

## パスの記述
CLAUDE.md・SESSION.md 等でローカルパスを書くときは `~` 表記を使う（`/Users/<user>/` は共同編集者の環境で壊れる）。

## 4 層モデルの依存ルール

claude-config の 4 層モデル (audience の広さ順に numbering、`public ⊃ collaborator set ⊃ owner ⊃ machine-local`):

| # | 層 | 例 | Audience | 依存可能先 |
|---|---|---|---|---|
| 1 | 共通規約 | claude-config | public / shared | — |
| 2 | 共有プロジェクト層 (このリポ) | private repo with collaborators | collaborator set | **layer 1 のみ** |
| 3 | 個人層 (secret 配置を含む) | `<owner>-prefs/` / 個人 secret repo / `~/.secrets/` | owner only | layers 1, 2 |
| 4 | 揮発メモリ | `~/.claude/.../memory/` | local machine | any |

> [`docs/personal-layer.md`](../docs/personal-layer.md) §「What is the personal layer?」 が canonical、本表は reading mirror (= 後述の §機能 literal と reading mirror の区別 の慣例に従う)。新規列追加・layer 番号変更時は personal-layer.md 側を真正本として更新する。
>
> **「依存可能先」の読み方**: ここで列挙されているのは **rule 上参照してよい上限** (= audience containment で許される上限) であって、**実際にどこまで依存するか** は各リポの judgment call。例えば layer 3 (個人層) は rule 上 layer 1 + 2 に依存可能だが、現実には layer 1 (claude-config) のみ参照しているケースが普通 (= 自分のリポを personal layer から自分の collaborator リポに参照する必要は少ない)。「依存可能」 ≠ 「実依存」 なので混同しない。

**Core rule**: each layer may only depend on layers whose audience contains its own (= 番号が小さい層を参照できる、大きい層は参照できない)。

具体的に共有プロジェクト層 (= layer 2) は **layer 1 (共通規約) のみ依存可、layer 3 (個人層) と layer 4 (揮発メモリ) には依存禁止**。理由: 共同編集者は所有者の個人層も machine-local memory も見られないため、依存すると collaborator 環境で動作が破綻する。

具体的には CLAUDE.md / DESIGN.md / README.md など共同編集者が触れるファイルに以下を **絶対に書かない**:

- 所有者の他の private リポへの参照 (= layer 3 の他リポ名)
- 所有者の個人層内ファイルへのファイルパス参照 (= layer 3 への literal path)
- 所有者個人のメール文体・身元情報のインライン (= layer 3 のデータ)
- 所有者個人のカレンダー ID・アカウント ID (= layer 3 のデータ)
- 所有者個人の secret 配置の絶対パス (例: `~/.secrets/<owner-specific>-token`、所有者固有のクラウドストレージ path) — secret は layer 3 のサブセット
- `/Users/<owner>/` のような絶対パス
- 揮発メモリへの参照 (= layer 4、machine-local。collaborator は持っていない)

これらは layer 3 (個人層、cascade 経由で勝手に上書き) または layer 4 (memory) に置く。共有プロジェクト層は **standalone で成立する** こと (= 操作的定義は次節 「『standalone で成立』 の操作的定義」 参照)。

### 公開前の Audit

共同編集者にリポを渡す前に、以下の grep を 0 件確認:

```bash
# 所有者個人の他リポ参照
grep -rn '<owner>-prefs\|<other-private-repo-1>\|<other-private-repo-2>' --exclude-dir=.git .

# 所有者個人の絶対パス
grep -rn "/Users/<owner>" --exclude-dir=.git .

# 所有者個人のメール・カレンダー識別子
grep -rE '<owner-personal-calendar-id>|<owner-personal-email>' --exclude-dir=.git .
```

`<owner>` 等は実際の所有者・リポ名に置き換える。所有者は自分の個人層に「公開禁止のキーワード一覧」を持っておくと監査が楽。

> **Note**: 上記の手動 audit は hook 未導入の共同編集者向けの fallback。
> 個人運用では `hooks/public-leak-guard.sh` (PreToolUse) と
> `scripts/public-precommit-runner.sh` (pre-commit) で自動化済み。
> 設計詳細は `DESIGN.md` §公開リポ leak 防止。

## 「standalone で成立」 の操作的定義

「standalone で成立」は **完全自己完結** ではなく、**標準 dev environment + 明示された外部依存** で動作する状態を指す。

### 標準 dev environment

claude-config が想定する標準 dev environment:

- macOS or Linux + git + git-crypt + GitHub CLI
- claude-config の `setup.sh` が走る (= 主要依存 tool が揃う)

Windows は `cp` + post-merge hook で claude-config 自体は動くが、shell 系スクリプトの動作保証は別途 (各 shared リポで明示)。

### 許容される外部依存と doc 明示義務

shared 層が依存していい外部リソースと、その doc 明示義務:

| 依存先 | 例 | 明示義務 |
|---|---|---|
| 第三者 SaaS | GitHub Actions / Discord API / Google Calendar | 落ちた時の制約と回避策を CLAUDE.md に明記 |
| layer 3 (個人層 / secret) への interface | 環境変数名 / GitHub Actions secret 名 / generic な path 表現 (`~/.secrets/<service>-token`) | 具体 owner literal は layer 3 に隔離、shared 層には interface 名のみ |
| OS 固有機能 | macOS only スクリプト (Hammerspoon, launchd 等) | リポの CLAUDE.md / README に「macOS 限定」明示 |
| 帯域・Network 制約 | 組織 NW での外部 API ブロック | 制約と回避策 (例: GitHub Actions 経由) を明示 |

### 判定基準

**共同編集者が clone → setup.sh を走らせた時、何が動いて何が動かないかが doc から判断できる** ことが standalone 要件の本質:

- ✅ 動く例: cron 駆動の自動 job (= GitHub Actions)、yaml/script 編集 + push、機能サマリの参照
- ⚠️ 制約付きで動く例: secret 必要操作 (owner 依頼経路に従う、具体的には `conventions/discord-bot.md §「Token 共有プロトコル」` 参照)、macOS only スクリプト (他 OS では skip)
- ❌ doc 不明示で動かない = layer 違反: 共同編集者がトラブルシュートで詰む状態

### operational 完結性の文書化義務

「standalone で成立」は **動作要件**であり、**operational 完結性 (= collaborator 単独で全操作可能) とは別**。secret 等を要する操作を意図的に owner-only にしている場合、共有層の CLAUDE.md に「< 該当操作 > は owner 依頼経路」と明記すれば、standalone 要件と矛盾しない (= 共同編集者が「自分は何ができないか」を doc から判別できる)。明記がないと collaborator が試行錯誤で行き止まりを発見する cost が発生する。

## 機能 literal と reading mirror の区別

共有層の literal は 2 種類あり、混同すると drift リスクが発生する:

| 種類 | 例 | 性質 |
|---|---|---|
| **機能 literal** | workflow yaml の identifier dict / script の URL / 設定ファイルの key | 機械が読むので変更すると動作が壊れる = 真正本 |
| **reading mirror** | CLAUDE.md / README.md の identifier テーブル | 人間 reading 用、機能上は不要だが doc としてあると便利 |

### drift 対策

reading mirror には **真正本ポインタ** を併記する:

```markdown
| Channel | ID |
|---|---|
| #foo | 1234 |

> `discord-fetch.yml` の `channels` dict が canonical、本テーブルは reading mirror。
> 新規追加・rename 時は yaml 側を真正本として更新する。
```

これで次に編集する人が「真正本 → mirror」の順で更新できる。mirror が drift しても致命傷にはならないが、grep で検出しにくいバグ源。

### 多層 mirror

同じ identifier が 機能 literal + shared mirror + personal mirror の 3 段に重複する場合 (例: Discord channel ID = workflow yaml + shared CLAUDE.md + personal layer の reference doc) は mirror を 1 段に絞ることを優先検討する。ただし「auto-load される doc に書いておけば Claude が即参照できる」便宜と weight する — 残す場合は各 mirror に真正本ポインタを忘れず付ける。

## Collaborator の招待（GitHub）

GitHub UI 経由でも可だが、`gh` CLI で 1 行で完結する:

```bash
# write 権限（一般的な共同編集者）
gh api -X PUT repos/<owner>/<repo>/collaborators/<username> -f permission=push

# read 権限のみ
gh api -X PUT repos/<owner>/<repo>/collaborators/<username> -f permission=pull

# admin (鍵管理者など)
gh api -X PUT repos/<owner>/<repo>/collaborators/<username> -f permission=admin
```

実行後、対象ユーザーには GitHub から invite メールが届き、accept すると collaborator になる。状態確認:

```bash
# 受諾済みの collaborator 一覧
gh api repos/<owner>/<repo>/collaborators

# 未受諾の pending invitations
gh api repos/<owner>/<repo>/invitations
```

`permission` の選択指針: 卒論・共同論文等の write 必要なケースは `push`。`maintain` は branch 保護や release 管理を任せる場合のみ。`admin` は鍵管理者か co-owner だけ。

## 共有 git-crypt 鍵パターン

共有プロジェクトを git-crypt で暗号化したい場合、**個人鍵とは別の鍵**を作って共同編集者と共有する。**鍵配布は openssl 暗号化 backup をクラウドストレージ (Dropbox 等) に置き、`.claude/git-crypt-backup` + `setup.sh` Step 5b-pre による全自動復元を canonical にする** (詳細: [`docs/git-crypt-guide.ja.md`](../docs/git-crypt-guide.ja.md) §共有リポでの自動復元)。

### 鍵の生成 + 配布 (initiator 側、初回のみ)

1. リポで `git-crypt init` → 内部鍵生成
2. `git-crypt export-key /tmp/<project-name>.key && chmod 600 /tmp/<project-name>.key`
3. 鍵を openssl で暗号化してクラウドストレージ共有フォルダに配置:
   ```bash
   /usr/bin/openssl enc -aes-256-cbc -pbkdf2 -salt \
     -in /tmp/<project-name>.key \
     -out <shared-storage>/<project-name>.key.enc
   shred -u /tmp/<project-name>.key   # 平文を即削除
   ```
4. 強いパスフレーズを共同編集者に **out-of-band で共有** (対面 / Signal 等。GitHub / クラウドストレージ / メール経由は禁止)
5. リポに `.claude/git-crypt-backup` を作成、暗号化ファイル名 (= `<project-name>.key.enc`) を 1 行で記載 ← これが setup.sh の検索キー
6. `~/.secrets/<project-name>.key` をローカルに配置して `git-crypt unlock` で動作確認

### 共同編集者向けの SETUP.md

共同編集者が新マシンで onboarding するための walkthrough は、**`SETUP.md` (リポ root)** に置く。CLAUDE.md は毎セッション auto-load されるため full walkthrough を入れるとコスト増、cold reference として SETUP.md に分離する。

- テンプレ: [`templates/shared-project/SETUP.md.template`](../templates/shared-project/SETUP.md.template) を copy → このリポ固有のパラメータ (encrypted backup ファイル名 / Dropbox path / local key path / passphrase 受領経路 / plaintext test file) を埋める
- 配置: **必ずリポ root**。`docs/**` を git-crypt 暗号化対象にしている場合、`docs/SETUP.md` だと未 unlock の collaborator が読めない catch-22
- CLAUDE.md 側の git-crypt セクションは **SETUP.md への 1-2 行ポインタ + 反パターン警告 (手動 openssl から始めない) のみ**。例:
  ```markdown
  **git-crypt 有効** (`<encrypted-paths>` のみ暗号化)。
  - 復号後の日常運用: `git-crypt unlock ~/.secrets/<project-name>.key`
  - **新マシン初回セットアップ → [SETUP.md](SETUP.md) を必ず読んでから進める**。`cd ~/Claude/claude-config && ./setup.sh` で全自動。⚠️ **手動 `openssl enc -d ...` から始めない** (path 誤りで bad-decrypt 残骸事故が過去あり、SETUP.md §反パターン警告 参照)
  ```

SETUP.md.template は復号失敗事故 (`docs/git-crypt-guide.ja.md` §共有リポでの自動復元 「共同編集者向け運用」項の手動経路 anti-pattern bullet 群) の 5 段アンチパターン全てに対する防御 (反パターン警告 + 推奨経路 setup.sh 最優先 + 手動 fallback の Step 0 事前確認 / Step 2 事後確認) を組み込んでいる。**項目を削らず内容だけ埋める**こと。

### 暗号化スコープ最小化を検討する

`.gitattributes` を `private/** filter=git-crypt diff=git-crypt` 1 行に絞ると、機微な情報のみ `private/` に入れて他は平文で扱える。鍵管理コストと audit のしやすさが大きく改善される。**逆に `docs/**` を暗号化対象にすると、SETUP.md を `docs/` に置けない catch-22 になるため SETUP.md は必ず repo root** (上記 §共同編集者向けの SETUP.md 参照)。詳細は [`docs/git-crypt-guide.md`](../docs/git-crypt-guide.md) 参照。

### 鍵のローカルパスは共同編集者ごとに異なる (補助的、レガシー)

`setup.sh` Step 5b-pre が `.claude/git-crypt-backup` + クラウドストレージ find で鍵を自動配置するため **path 知識自体が不要** になっており、これが canonical recovery 経路。

ただし個人層 (e.g., `<your>-prefs/`) を持つユーザは補助的に `shared-project-keys.md` レジストリで「自分のマシンに何の鍵があるか」を管理してもよい。schema:

```markdown
| Project | Local key path | `.claude/git-crypt-backup` の中身 |
|---|---|---|
| <project-name> | ~/.secrets/<project-name>.key | <project-name>.key.enc |
```

このレジストリは Claude が「どの鍵が手元にあるか」を一覧把握する用途であり、unlock 自体は setup.sh が自動で行うため依存ではない (**共有プロジェクト層は個人層に依存しない** 4 層モデルが守られる)。個人層の placeholder (`<workplace_short>` 等) は path 解決には**使わない** (誤展開事故防止 — `docs/git-crypt-guide.ja.md` §共有リポでの自動復元 参照)。

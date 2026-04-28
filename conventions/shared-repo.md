# 共有リポ規約 — Shared Project Layer

共同編集者がいるリポで適用。CLAUDE.md から参照: `~/Claude/claude-config/conventions/shared-repo.md`

このファイルは Claude Code 4 層モデルの **層 3（共有プロジェクト層）** の規約。詳しい層モデルは [`docs/personal-layer.md`](../docs/personal-layer.md) を参照。

## Git workflow（必須）

### セッション開始時
「作業開始」「スタート」等の合図があったら:
1. `git status` で状態チェック
   - **未コミット変更あり** → 「前回の変更が未 commit です。先に commit & push しますか？」
   - **未 push コミットあり** → 「前回の commit が未 push です。先に push しますか？」
2. `git pull` でリモートと同期（コンフリクト発生時はユーザーと解決）
3. **他所からの open PR を確認**: `gh pr list` (もしくは `gh pr list --state open`) を実行し、共同編集者・外部から来ている open PR があればユーザーに提示する。具体的には:
   - 件数 0 → 何も言わずに次へ
   - 1 件以上 → タイトル・著者・更新日を一覧で出して「先にレビューしますか？それとも今のタスクを進めますか？」と判断を仰ぐ。レビュー先行を選ばれたら `gh pr view <num>` / `gh pr diff <num>` で内容を確認、不要な差分でなければ review コメントを準備
   - **判断材料**: 競合可能性（PR が触っているファイルと今のタスクが重なるか）、緊急度（CI 失敗・レビュアー unblock 待ち）、author（外部からなら原則優先）
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

共有プロジェクト層（このリポ）は **層 1（共通規約 = claude-config）にのみ依存**できる。**層 2（個人層 = `<owner>-prefs/`）には依存禁止**。理由: 共同編集者は所有者の個人層を見られないため、依存すると collaborator 環境で動作が破綻する。

具体的には CLAUDE.md / DESIGN.md / README.md など共同編集者が触れるファイルに以下を **絶対に書かない**:

- 所有者の他の private リポへの参照
- 所有者の個人層内ファイルへのファイルパス参照
- 所有者個人のメール文体・身元情報のインライン
- 所有者個人のカレンダー ID・アカウント ID
- `/Users/<owner>/` のような絶対パス

これらは個人層（あれば cascade 経由で勝手に上書き）に置く。共有プロジェクト層は **standalone で成立する** こと。

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

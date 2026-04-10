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
3. リマインダー表示: **「作業が終わったら commit & push を忘れずに！」**

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

共有プロジェクトを git-crypt で暗号化したい場合、**個人鍵とは別の鍵**を作って共同編集者と共有する。

### 鍵の生成と配布

1. リポで `git-crypt init` → 内部鍵生成
2. `git-crypt export-key <somewhere>/<project-name>.key`
3. 共同編集者全員がアクセスできる場所（チーム共有 Dropbox フォルダ等）に鍵をコピー
4. 共同編集者は各自その場所から鍵を取得し、好きなローカルパスに保存
5. `git-crypt unlock <local-path>` で復号

### 暗号化スコープ最小化を検討する

`.gitattributes` を `private/** filter=git-crypt diff=git-crypt` 1 行に絞ると、機微な情報のみ `private/` に入れて他は平文で扱える。鍵管理コストと audit のしやすさが大きく改善される。詳細は [`docs/git-crypt-guide.md`](../docs/git-crypt-guide.md) 参照。

### 鍵のローカルパスは共同編集者ごとに異なる

CLAUDE.md には**単一のコマンド例**を書きつつ、ユーザごとの実パスは個人層側の `shared-project-keys.md` で管理する仕組みにする:

CLAUDE.md 側の記述例:
```markdown
**復号**: `git-crypt unlock <your-key-path>`
- 鍵の正本: <共有フォルダ>/<project>.key
- パスは個人層の `shared-project-keys.md` に登録（Claude が自動で拾う）
- 個人層を持たない場合は `~/.secrets/<project-name>.key` に置けば fallback
```

`shared-project-keys.md` の schema:
```markdown
| Project | Local key path |
|---|---|
| <project-name> | ~/.secrets/<project-name>.key |
```

これで Claude は共有プロジェクトに入った時に個人層の `shared-project-keys.md` を参照し、該当エントリのパスで自動 unlock できる。なくても fallback で動作する（**共有プロジェクト層は個人層に依存しない**ことが守られる）。

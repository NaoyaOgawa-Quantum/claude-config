# ~/Claude リポジトリ規約

新規リポ作成時・既存リポ整備時に参照する標準規約。
最終更新: 2026-03-16

---

## 1. リポジトリ作成手順

```bash
# 1. GitHub に private リポ作成 + clone
cd ~/Claude
gh repo create odakin/<name> --private --description "<説明>" --clone

# 2. ブランチ名を main に統一
cd <name>
git branch -M main

# 3. 必須ファイルを作成（後述のテンプレート参照）
# 4. initial commit + push
git add . && git commit -m "Initial commit: <概要>"
git push -u origin main
```

## 1.5. 未 clone リポの同期

~/Claude 以下を最新にする際、GitHub 上の odakin アカウントにあるがローカルに clone されていないリポがあれば取得する。

```bash
# 1. GitHub 上の odakin リポ一覧を取得
gh repo list odakin --limit 50 --json name

# 2. ~/Claude に存在しないリポを clone
cd ~/Claude
gh repo clone odakin/<name>
```

**注意**: clone 後はセクション9のリポ一覧にも追記すること。

---

## 2. 必須ファイル

| ファイル | 役割 | 必須度 |
|---------|------|--------|
| `CLAUDE.md` | **永続的な指示書**。プロジェクト概要、構造、実行方法、再開手順。セッションをまたいで不変。 | ★★★ |
| `SESSION.md` | **揮発的な作業ログ**。現在の作業状態、直近の決定事項、次のステップ。作業の進行に応じて更新。 | ★★★ |
| `.gitignore` | ビルド成果物・OS/エディタファイル・機密情報の除外 | ★★★ |
| `docs/` | 参考資料（PDF、ノート等）を格納するディレクトリ | ★★ |

### CLAUDE.md と SESSION.md の役割分担

- **CLAUDE.md = 憲法 + 自動復帰の入口**：プロジェクトの構造・ルール・実行方法。構造変更時のみ更新。autocompact 後に最初に読まれるファイル。
- **SESSION.md = 生きた作業状態**：今何をしているか、何が終わったか、次に何をするか。**作業の進行に応じて自動的に更新される**。
- 原則: CLAUDE.md は「どうやるか」、SESSION.md は「今どこにいるか」。

---

## 3. 自動更新プロトコル（全リポ共通・必須）

### SESSION.md の自動更新タイミング

**以下のタイミングで SESSION.md を必ず更新する。人間に言われなくても自動で行う。**

| タイミング | 更新内容 |
|-----------|---------|
| タスク完了時 | 完了したタスクを `[x]` にし、成果物・変更ファイルを記録 |
| 重要な判断時 | ユーザーの決定・方針変更を「直近の決定事項」に記録 |
| ファイル作成/大幅変更時 | 変更したファイルのパスと概要を記録 |
| エラー・ブロッカー発生時 | 問題の内容と状態を記録 |
| 長い作業の区切り | 中間状態を記録（autocompact に備える） |
| **外部公開・デプロイ時** | **日時・コミット・内容を SESSION.md のデプロイ履歴テーブルに追記**（zenn push、論文投稿、arXiv 投稿等） |

### SESSION.md 更新時の整合性チェック（必須）

SESSION.md を更新するたびに、以下を確認すること：

1. **直前の議論との矛盾がないか** — 会話で訂正・修正した内容が SESSION.md に正しく反映されているか
2. **コードと記述の一致** — スクリプトの出力や検証結果と、SESSION.md の記述が食い違っていないか
3. **ファイル構成の正確性** — 実際のファイル一覧と SESSION.md のコードベース構成が合っているか
4. **古い情報の残留** — 訂正済みの結論が「以前の誤った記述」のまま残っていないか

矛盾を見つけたら、更新前に修正すること。SESSION.md は autocompact 後の唯一の復帰情報なので、不正確な記述は致命的。

### CLAUDE.md の更新タイミング

**以下の場合にのみ CLAUDE.md を更新する:**

| タイミング | 更新内容 |
|-----------|---------|
| リポ構造が変わったとき | 構造図 (tree) を更新 |
| 新しい実行手順が確定したとき | 実行環境セクションを更新 |
| Phase が大きく進んだとき | "How to Resume" の手順を更新 |

### autocompact 復帰フロー

autocompact が発生すると、Claude Code は CLAUDE.md を自動的に読み込む。
CLAUDE.md の冒頭に復帰手順を書いておくことで、自動的に作業を再開できる。

```
autocompact 発生
  → CLAUDE.md 自動読み込み
  → "How to Resume" セクションに従い SESSION.md を読む
  → SESSION.md の「現在の状態」「次のステップ」から作業を継続
```

**重要**: この復帰が機能するためには、SESSION.md が常に最新である必要がある。
だから上記の自動更新タイミングを守ることが不可欠。

### プッシュ前チェック（全リポ共通・必須）

**`git push` の前に以下を確認する。人間に言われなくても自動で行う。**

#### 整合性・無矛盾性
1. **SESSION.md が最新か**: 現在の作業状態・完了タスク・次のステップが実態と一致しているか
2. **CLAUDE.md が最新か**: そのセッションで構造変更・手順変更・Phase 進行があった場合、CLAUDE.md に反映されているか
3. **CONVENTIONS.md との整合性**（CLAUDE.md を更新した場合のみ）: テンプレート構成・必須セクション・命名規約と矛盾しないか
4. **CONVENTIONS.md 自体を変更した場合**: 既存リポの CLAUDE.md に波及する変更がないか確認し、必要なら影響リポの CLAUDE.md も更新

#### 効率性
5. **冗長な記述がないか**: 同じ情報が複数箇所に書かれていないか（正本を1つに決める）
6. **不要になった記述がないか**: 完了済みの TODO、古い手順、使われていない設定等を整理
7. **指示が具体的で実行可能か**: 曖昧な指示や「後で決める」が放置されていないか

```
push 前チェックフロー:
  1. SESSION.md の「現在の状態」「次のステップ」を実態に合わせて更新
  2. CLAUDE.md の更新が必要か判断 → 必要なら更新
  3. CLAUDE.md を更新した場合 → CONVENTIONS.md と矛盾がないか確認
  4. 効率性チェック → 冗長・陳腐化・曖昧な記述がないか確認
  5. commit → push
```

**注意**: 軽微な変更（typo修正、コメント追加等）で CLAUDE.md に影響がない場合、ステップ 2-4 はスキップしてよい。

---

## 4. CLAUDE.md テンプレート

```markdown
# <プロジェクト名>

## 概要
<1-2文でプロジェクトの目的を説明>

## リポジトリ情報
- パス: `~/Claude/<name>/`
- ブランチ: `main`
- リモート: `odakin/<name>` (private, GitHub)

## 構造
\`\`\`
<name>/
├── CLAUDE.md
├── SESSION.md
├── src/
├── docs/
└── ...
\`\`\`

## 実行環境
- 言語: <Python 3.x / LaTeX / etc.>
- 依存: <pip install ... / brew install ... / なし>
- 実行: <コマンド例>

## How to Resume（autocompact 復帰手順）
**autocompact 後・新規セッション開始時、必ずこの手順を実行:**
1. `SESSION.md` を読む → 現在の作業状態と次のステップを把握
2. SESSION.md の「次のステップ」に従って作業を継続
3. 不明点があればユーザーに確認

## 自動更新ルール（必須）
以下を人間に言われなくても自動で行う:
- タスク完了時 → SESSION.md を更新（完了マーク + 成果物記録）
- 重要な判断時 → SESSION.md に決定事項を記録
- ファイル作成/大幅変更時 → SESSION.md に記録
- push 前 → SESSION.md / CLAUDE.md が実態と一致しているか確認（詳細は CONVENTIONS.md §3）
- CLAUDE.md のルールの詳細は `~/Claude/CONVENTIONS.md` 参照

**注意（共有リポの場合）**: 共同編集者は CONVENTIONS.md を持っていない。
共有リポでは上記の自動更新ルールと SESSION.md ルール（CONVENTIONS.md §3）を
CLAUDE.md 内に直接記述すること（§14 参照）。
```

---

## 5. SESSION.md テンプレート

```markdown
# <プロジェクト名> Session

## 現在の状態
**作業中**: <今やっていること or 待ち状態の説明>

### タスク進捗
- [x] <完了したタスク1>
- [ ] <進行中のタスク2> ← **ここから再開**
- [ ] <未着手のタスク3>

## 次のステップ
1. <最も優先度の高い次のアクション>
2. <その次>

## 直近の決定事項
- <日付>: <決定内容>

## 作業ログ
### <日付>
- <何をしたか>
- 変更ファイル: `path/to/file`
```

**SESSION.md の書き方ルール:**
- 「現在の状態」と「次のステップ」を常に最上部に置く（復帰時に最初に目に入るように）
- 完了タスクは `[x]`、進行中は `[ ]` + 「← ここから再開」マーカー
- 作業ログは下に追記していく（上が最新状態、下が履歴）

---

## 6. .gitignore 標準構成

プロジェクトの言語に応じて以下を組み合わせる。
**注意**: LaTeX / .DS_Store は `~/.gitignore_global` でグローバル除外済み（§8 参照）。ローカル専用リポではこれらを省略してよい。**共有リポ**では共同編集者のために含めること。

```gitignore
# === 共通（全プロジェクト） ===
.DS_Store
Thumbs.db
*~
*.swp
*.swo
.claude/

# === Python ===
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# === LaTeX ===
*.aux
*.bbl
*.blg
*.log
*.out
*.toc
*.synctex.gz
*.synctex
*.fls
*.fdb_latexmk

# === Mathematica ===
*.mx

# === Node.js ===
node_modules/
package-lock.json  # 必要なら残す

# === 出力ファイル ===
plot_output.png
*.tmp
```

---

## 7. ディレクトリ命名規約

| パターン | 用途 | 例 |
|---------|------|-----|
| `src/` | メインソースコード・原稿 | LaTeX, Python スクリプト |
| `docs/` | 参考資料・外部文献 | PDF, メモ |
| `referee/` | レフェリーレポート（論文リポ） | レポート PDF |
| `analyses/` | 解析スクリプト・ノートブック | Mathematica, Jupyter |
| `tools/` | ユーティリティスクリプト | パーサー、変換器 |
| `scripts/` | 自動化スクリプト | ビルド、デプロイ |

---

## 8. Git 規約

- **ブランチ**: `main` に統一（`master` は使わない）
- **コミットメッセージ**: 英語、1行目は動詞始まり（`Add`, `Fix`, `Update`）
- **大きなファイル**: PDF 等で push が失敗したら `git config http.postBuffer 157286400`
- **バージョン管理**: ファイル名に番号をつけない（`fixed1`, `fixed2` 等は禁止）。git がバージョン管理する。
- **機密情報**: `.env`, `credentials`, 個人情報を含むファイルはコミットしない
- **コミット後は常に push**: `git commit` したら `git push` まで行う（push 前チェック §3 を挟んでから push する。commit だけで放置しない、という意味）。
- **セッション終了時は必ず commit + push**: 作業が一段落したとき・ユーザーとの会話が終わりそうなとき、未コミットの変更があれば commit & push してから終了する。変更を手元に残したまま終わらない。
- **グローバル gitignore**: `~/.gitignore_global` で TeX 中間ファイル（*.aux, *.bbl, *.blg, *.log, *.out, *.synctex.gz 等）と .DS_Store をグローバルに除外済み。**共有リポジトリ**の `.gitignore` にも TeX 除外ルールを含める（共同編集者はグローバル設定を持っていないため）。ローカル専用リポはグローバルに任せてプロジェクト固有のみでOK。

---

## 9. リポ一覧

| リポ | パス | 用途 | ブランチ |
|------|------|------|---------|
| multi-agent-shogun | ~/Claude/multi-agent-shogun | マルチエージェント開発基盤 | main |
| einstein-cartan | ~/Claude/einstein-cartan | EC重力理論ゲージ不変性検証 | main |
| epstein-article | ~/Claude/epstein-article | エプスタイン記事（zenn） | main |
| ejp-revision | ~/Claude/ejp-revision | EJP論文改訂 | main |
| bayes-kai | ~/Claude/bayes-kai | ベイズ統計・中性子寿命 | main |
| kakutei-shinkoku-2025 | ~/Claude/kakutei-shinkoku-2025 | 確定申告2025 | main |
| mhlw-ec-pharmacy-finder | ~/Claude/mhlw-ec-pharmacy-finder | 厚労省EC薬局検索 | main |
| physics-research | ~/Claude/physics-research | 物理研究 | main |
| ishida-tsutsumi-map | ~/Claude/ishida-tsutsumi-map | 石田堤マップ | main |
| codex-shogun-system | ~/Claude/codex-shogun-system | Codex Shogun システム | main |
| EMrel | ~/Claude/EMrel | 電磁相対論 | main |
| webGL-test | ~/Claude/webGL-test | WebGLテスト | main |
| claude-config | ~/Claude/claude-config | 共通設定（CONVENTIONS.md等） | main |
| arxiv-digest | ~/Claude/arxiv-digest | arXiv ダイジェスト | main |
| gmail-mcp-config | ~/Claude/gmail-mcp-config | Gmail MCP 設定 | main |

**注意**: odakin のリポのみ操作する。yohey-w は絶対に触らない。

---

## 10. 安全規則（絶対厳守）

以下のルールは何があっても破ってはならない。

1. **自分が作っていないファイルやディレクトリを削除する前に、必ず `ls` で中身を確認しユーザーに提示する。** 自分が当該セッションで作ったものは確認不要。
2. **ユーザーの既存データを削除するときはリネーム (`mv old old.bak`) を優先提案する。**
3. ユーザーにコマンドを提示する際は、破壊的な操作が含まれていないか必ず確認する。
4. **force push 禁止**: `git push --force` は使わない。必要なら `--force-with-lease`。
5. **機密ファイル**: コミットしない（詳細は §8 Git 規約参照）。
6. **ファイルの重複禁止**: 同じファイルを複数リポに置かない。1つの正本を決める。
7. **破壊的操作は必ず事前確認**: リポ削除、ブランチ削除、ファイル一括削除、`git reset --hard` など不可逆な操作を行う前に、必ずユーザーに確認を取る。暗黙の了解で実行しない。

---

## 11. エディタ連携

- **VS Code** (Visual Studio Code) と Claude Code を連携して使用
- 拡張: `anthropic.claude-code`（公式）、`ms-ceintl.vscode-language-pack-ja`（日本語）
- `EDITOR=code --wait` 設定済み — Claude Code からファイルを VS Code で開ける
- VS Code で `~/Claude` を開けば、Claude Code と同じファイルをシームレスに編集可能

---

## 12. Markdown / GFM ルール（zenn.dev 等）

zenn.dev を含む多くのプラットフォームは GFM (GitHub Flavored Markdown) を使っている。
日本語テキストで `**bold**` が壊れるケースがあるので、以下を常に意識すること。

### GFM の `**` delimiter ルール

**開き `**`（left-flanking delimiter run）の条件:**
1. `**` の直後が空白でない
2. `**` の直後が句読点なら、`**` の直前が空白か句読点でなければならない

**閉じ `**`（right-flanking delimiter run）の条件:**
1. `**` の直前が空白でない
2. `**` の直前が句読点なら、`**` の直後が空白か句読点でなければならない

### 日本語で壊れるパターンと対処

| パターン | 問題 | 対処 |
|---|---|---|
| `は**「bold」**` | 開き `**` の直後が `「`（句読点）、直前が `は`（非空白・非句読）→ left-flanking 条件2不成立 | `は **「bold」**`（`**` の前にスペース追加） |
| `（H3）**が` | 閉じ `**` の直前が `）`（句読点）、直後が `が`（非空白・非句読）→ right-flanking 条件2不成立 | `（H3）** が`（`**` の後にスペース追加） |
| `」**と` | 同上。`」` も句読点扱い | `」** と`（`**` の後にスペース追加） |
| `**bold **next` | 閉じ `**` の直前がスペース → right-flanking 条件1不成立 | `**bold**next`（スペースを除去） |

### 注意事項

- `**` の前にスペースを入れる GFM 修正は **開き `**` のみ** に適用する。閉じ `**` の前にスペースを入れると right-flanking が壊れる
- `**` が開きか閉じかはコンテキスト依存。正規表現で機械的に区別するのは困難。**自動修正は最小限に留め、目視確認を併用する**
- CJK 文字は GFM 上「句読点でも空白でもない」通常文字として扱われる。したがって **閉じ `**` の直前が全角句読点（`）」】。、`等）で直後が CJK 文字** の場合、right-flanking 条件2が不成立になる。対処: 閉じ `**` の直後にスペースを入れる
- **既に `**...**` 内にあるテキストに `**` を追加してはいけない**。`**外側**内側テキスト**外側**` のようになると `****` が発生し、bold が完全に壊れる。プログラムで bold を追加する際は、対象位置の前にある `**` の数を数え、奇数なら既に bold 内なのでスキップする

---

## 13. プロット・画像出力ルール

- **ファイル名は内容を反映する**（例: `neutron_bottle_beam_comparison.png`）。バージョン番号は使わない（git が履歴を管理する）
- 作業用の `plot_output.png` は `.gitignore` に入れてよい。内容を反映した名前のファイルをコミット対象とする
- 生成後は `open` コマンドでシステムのプレビューを開く

---

## 14. 共有リポジトリの CLAUDE.md 同期ルール

共有リポジトリ（GitHub 等で他の人と共同編集するもの）を作るとき、Claude が自動で以下を行う：
1. プロジェクトの `CLAUDE.md` に SESSION.md ルールを含める（共同編集者にも適用されるように）
2. SESSION.md ルールの内容は CONVENTIONS.md §3 のものと同一にする
3. CONVENTIONS.md の SESSION.md ルールを変更した場合は、既存の共有プロジェクトの CLAUDE.md も同様に更新する

**ユーザーの手作業は不要。Claude が一貫性を維持する。**

# claude-config

Shared conventions and setup for managing multiple projects with [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## What This Is

A central configuration repository that provides:

- **CONVENTIONS.md** — Project-wide rules for file structure, Git workflow, session management, and safety guardrails
- **setup.sh** — One-command bootstrap: creates symlinks and clones all your repos
- **gfm-rules.md** — Quick reference for GitHub Flavored Markdown edge cases with CJK text

The idea is simple: keep one authoritative set of conventions and symlink it into your workspace, so every project follows the same rules without duplication.

## How It Works

```
~/Claude/
├── CONVENTIONS.md → claude-config/CONVENTIONS.md  (symlink)
├── claude-config/          # this repo
│   ├── CLAUDE.md           # project-specific instructions for this repo
│   ├── CONVENTIONS.md      # the single source of truth
│   ├── README.md           # this file
│   ├── setup.sh            # bootstrap script
│   ├── gfm-rules.md        # CJK markdown reference
│   ├── LICENSE             # MIT
│   └── .gitignore
├── project-a/              # your projects
├── project-b/
└── ...
```

Each project's `CLAUDE.md` references `~/Claude/CONVENTIONS.md` for shared rules and adds only project-specific instructions.

## Quick Start

```bash
mkdir -p ~/Claude && cd ~/Claude
gh repo clone <your-username>/claude-config
cd claude-config && ./setup.sh
```

`setup.sh` will:
1. Create `~/Claude/CONVENTIONS.md` as a relative symlink to `claude-config/CONVENTIONS.md`
2. Clone all your GitHub repos into `~/Claude/` (skips repos already present)

## What's in CONVENTIONS.md

| Section | Summary |
|---------|---------|
| §1 Repo creation | `gh repo create` + initial commit recipe |
| §2 Required files | `CLAUDE.md` (permanent instructions), `SESSION.md` (volatile work log), `.gitignore` |
| §3 Auto-update protocol | When and how to update SESSION.md and CLAUDE.md automatically |
| §4-5 Templates | Starter templates for CLAUDE.md and SESSION.md |
| §6 .gitignore | Global and per-project ignore patterns |
| §7 Directory naming | Standard directory names (`src/`, `docs/`, `analyses/`, etc.) |
| §8 Git conventions | Branch strategy, commit messages, push protocol |
| §9 Safety rules | Guardrails for destructive operations, LaTeX editing, credentials |
| §10 Exhaustive verification | Mechanical checks before claiming completeness |
| §11 Miscellaneous | Image output, GFM CJK rules reference |

## Key Concepts

### CLAUDE.md vs SESSION.md

- **CLAUDE.md** = "How to work on this project" — structure, build commands, resume instructions. Updated rarely.
- **SESSION.md** = "Where we are right now" — current task, progress, decisions. Updated continuously.

This separation ensures that after context compression, Claude can always resume from SESSION.md without losing track of work.

### Push-Before-Check

Before every `git push`, Claude automatically verifies that SESSION.md and CLAUDE.md reflect the actual state of the project. This prevents documentation drift.

### Autocompact Recovery

When Claude Code's context window is compressed, the recovery flow is:

1. CLAUDE.md is loaded automatically (always in context)
2. "How to Resume" section directs Claude to read SESSION.md
3. SESSION.md provides current state, tasks, and next steps
4. Work continues seamlessly

This is why SESSION.md accuracy is critical — it's the sole recovery path after context compression.

### Safety Guardrails (§9)

The conventions include strict safety rules to prevent AI-assisted accidents:

- No destructive operations (force push, `reset --hard`, file deletion) without user confirmation
- No credentials or secrets in commits
- No modification of LaTeX equations without explicit approval (prevents hallucinated physics)
- Scope limited to owned repositories only

## Usage Tips

Practical patterns discovered through real-world use across 20+ projects.

### 1. Start every session fresh

Don't continue long conversations. Start a new session each time and say "resume project X." Claude reads CLAUDE.md → SESSION.md and picks up where you left off. This eliminates autocompact risk entirely.

**Prerequisite:** SESSION.md must be up to date (the auto-update protocol in §3 handles this).

### 2. The pre-push incantation

Before every push, say:

> "Check consistency, non-contradiction, and efficiency. Push."

Claude will cross-check your documentation against reality. In practice, **this catches something almost every time**: stale counts ("4 items" when there are now 6), circular references, duplicate headings, outdated status fields.

For public repos, add "safety":

> "Check consistency, non-contradiction, efficiency, and safety. Push."

Claude will grep for PII, private repo names, email addresses, and other sensitive data.

### 3. Say "think deeply" for non-trivial decisions

Claude defaults to quick answers. Explicitly asking it to think deeply yields trade-off analysis, alternative evaluation, and edge case consideration. Use this for architecture decisions, feature prioritization, and UI/UX choices — anywhere the answer isn't obvious.

### 4. Record the WHY, not just the WHAT

When you decide to implement (or not implement) a feature, record the reasoning in SESSION.md:

```markdown
# Bad
- "Don't implement X filter"

# Good
- "Don't implement X filter (2026-03-21) — data source is
  secondary (parser estimate, 97.1% coverage), no alternative
  for the ~290 unparseable entries, and no harm in not filtering"
```

Include the date. Circumstances change; dateless decisions look like permanent laws.

### 5. Use competitive analysis for feature planning

Ask Claude to fetch a competitor's site and analyze: "What are we losing to this site?" Then critically evaluate each gap — often, what looks like a weakness is already covered by existing features, or isn't worth implementing.

### 6. Save feedback memories for recurring mistakes

When Claude makes a mistake, save it as a feedback memory (`~/.claude/` memory system). Structure: rule → **Why** (what went wrong) → **How to apply** (when this kicks in). Also save when something works well — correction-only memory makes Claude overly cautious.

### 7. Single source of truth, no circular references

Pick exactly one place for each piece of information. Reference it from other places, but never duplicate the content. Always specify the section name, not just the file:

```markdown
# Bad — circular reference
CONVENTIONS.md: "Repo list is in MEMORY.md"
MEMORY.md: "Repo list is in CONVENTIONS.md §9"

# Good — single source with precise pointer
CONVENTIONS.md: "Repo list is in MEMORY.md, section 'Repo Index'"
MEMORY.md → [actual repo table lives here]
```

## Customization

Fork or clone this repo and edit CONVENTIONS.md to match your workflow. The conventions are written in Japanese, but the structure is language-agnostic — translate or adapt as needed.

Key things to customize:
- §1: Replace the GitHub username in repo creation commands
- §4: Adjust the CLAUDE.md template to your project structure
- §7: Modify directory naming conventions for your domain
- §9: Add or remove safety rules for your use case
- `setup.sh`: Change the GitHub username for repo cloning

## License

MIT

---

# claude-config（日本語）

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) で複数プロジェクトを管理するための共有規約とセットアップツール。

## 概要

- **CONVENTIONS.md** — ファイル構造、Git ワークフロー、セッション管理、安全規則をまとめた全プロジェクト共通の規約（正本）
- **setup.sh** — symlink 作成と全リポ clone を一発で行うブートストラップスクリプト
- **gfm-rules.md** — 日本語テキストの GFM bold 崩れ対策リファレンス

## 仕組み

```
~/Claude/
├── CONVENTIONS.md → claude-config/CONVENTIONS.md  (symlink)
├── claude-config/          # このリポ
│   ├── CLAUDE.md           # このリポ固有の指示書
│   ├── CONVENTIONS.md      # 規約の正本
│   ├── README.md           # このファイル
│   ├── setup.sh            # セットアップスクリプト
│   ├── gfm-rules.md        # CJK markdown リファレンス
│   ├── LICENSE             # MIT
│   └── .gitignore
├── project-a/              # 各プロジェクト
├── project-b/
└── ...
```

各プロジェクトの `CLAUDE.md` は `~/Claude/CONVENTIONS.md` を参照し、プロジェクト固有の指示のみ追記する。

## クイックスタート

```bash
mkdir -p ~/Claude && cd ~/Claude
gh repo clone <your-username>/claude-config
cd claude-config && ./setup.sh
```

`setup.sh` が行うこと:
1. `~/Claude/CONVENTIONS.md` → `claude-config/CONVENTIONS.md` の相対 symlink を作成
2. GitHub 上の全リポを `~/Claude/` 以下に clone（既存はスキップ）

## CONVENTIONS.md の構成

| セクション | 内容 |
|-----------|------|
| §1 リポ作成 | `gh repo create` + 初期コミット手順 |
| §2 必須ファイル | `CLAUDE.md`（永続的指示書）、`SESSION.md`（揮発的作業ログ）、`.gitignore` |
| §3 自動更新プロトコル | SESSION.md / CLAUDE.md の自動更新タイミングとルール |
| §4-5 テンプレート | CLAUDE.md / SESSION.md のスターターテンプレート |
| §6 .gitignore | グローバル・プロジェクト固有の除外パターン |
| §7 ディレクトリ命名 | 標準ディレクトリ名（`src/`, `docs/`, `analyses/` 等） |
| §8 Git 規約 | ブランチ戦略、コミットメッセージ、push プロトコル |
| §9 安全規則 | 破壊的操作・LaTeX 編集・機密情報に関するガードレール |
| §10 網羅性の検証 | 「全部」を主張する前の機械的検証 |
| §11 その他 | 画像出力、GFM CJK ルール参照 |

## 核となるコンセプト

### CLAUDE.md と SESSION.md の役割分担

- **CLAUDE.md** = 「このプロジェクトの作業方法」— 構造、ビルドコマンド、復帰手順。更新は稀
- **SESSION.md** = 「今どこにいるか」— 現在のタスク、進捗、決定事項。継続的に更新

この分離により、コンテキスト圧縮後も SESSION.md から確実に作業を再開できる。

### push 前チェック

`git push` の前に、SESSION.md と CLAUDE.md がプロジェクトの実態を反映しているか自動で確認する。ドキュメントの陳腐化を防ぐ。

### autocompact 復帰

Claude Code のコンテキストウィンドウが圧縮された場合の復帰フロー:

1. CLAUDE.md が自動読み込みされる（常にコンテキスト内）
2. 「How to Resume」セクションが SESSION.md の参照を指示
3. SESSION.md が現在の状態・タスク・次のステップを提供
4. シームレスに作業を継続

SESSION.md の正確性が重要な理由 — コンテキスト圧縮後の唯一の復帰パスだから。

### 安全規則（§9）

AI アシスタントによる事故を防ぐための厳格なルール:

- 破壊的操作（force push、`reset --hard`、ファイル削除）はユーザー確認なしに実行しない
- 機密情報・認証情報をコミットしない
- LaTeX の数式は明示的な承認なしに変更しない（物理のハルシネーション防止）
- 操作範囲は自分のリポジトリのみに限定

## 運用Tips

20以上のプロジェクトを実運用する中で見つけた実践パターン。

### 1. 毎回新規セッションで「〜を再開」

長い会話を続けない。毎回新しいセッションを立ち上げて「〇〇プロジェクトを再開」と言う。Claude が CLAUDE.md → SESSION.md を読んで、前回の続きから作業を再開する。autocompact のリスクがゼロになる。

**前提:** SESSION.md が常に最新であること（§3 の自動更新プロトコルが必須）。

### 2. push 前の呪文

push の前に毎回こう言う:

> 「整合性、無矛盾性、効率性をチェック。プッシュ。」

Claude がドキュメントとコードの齟齬を見つけて直す。**ほぼ毎回何か見つかる**: 古い件数、循環参照、見出し重複、ステータスの陳腐化など。

public リポでは「安全性」を追加:

> 「整合性、無矛盾性、効率性、安全性をチェック。プッシュ。」

個人情報・非公開リポ名・メールアドレス等の漏洩を grep でチェックしてくれる。

### 3. 「深く検討して」で浅い回答を防ぐ

Claude はデフォルトでさっさと答える。「深く検討して」と言うと、トレードオフ分析・代替案の比較・エッジケースの考慮が出てくる。正解が1つでない判断（設計、機能の要否、UIの配置など）で使う。

### 4. 決定事項の WHY を日付付きで記録

機能の採用/不採用を決めたら、**理由を含めて** SESSION.md に記録する:

```markdown
# 悪い例
- 「現在営業中」フィルターは実装しない

# 良い例
- 「現在営業中」フィルターは実装しない（2026-03-21）
  — 根拠が二次加工（パーサー推定、カバー率97.1%）で
  約290件が判定不能、代替なし、除外しなくても害がない
```

日付がないと、状況が変わっても永久に有効な不文律のようになってしまう。

### 5. 競合比較で機能のアイデア出し

Claude に競合サイトを分析させ、「何が負けているか」を聞く。ただし「負けている」= 実装すべきとは限らない。各項目について「深く検討して」を使い、本当に実装すべきかを検証する。

### 6. フィードバックメモリでミスを構造的に防ぐ

Claude Code の memory 機能にミスの教訓を保存する。構成: ルール → **Why**（何が起きたか）→ **How to apply**（いつ適用するか）。うまくいったパターンも記録する（修正ばかりだと Claude が過度に慎重になる）。

### 7. 正本を1つに決め、循環参照を潰す

情報の置き場所を1つだけ決め、他は参照にする。参照先はセクション名まで明記する:

```markdown
# 悪い例（循環参照）
CONVENTIONS.md: 「リポ一覧の正本は MEMORY.md」
MEMORY.md: 「リポ一覧は CONVENTIONS.md §9 が正本」

# 良い例（正本が1つ）
CONVENTIONS.md: 「リポ一覧の正本は MEMORY.md の『リポ一覧（正本）』セクション」
MEMORY.md → [実際のリポ一覧テーブルがここにある]
```

## カスタマイズ

フォークまたは clone して、CONVENTIONS.md を自分のワークフローに合わせて編集する。

カスタマイズのポイント:
- §1: リポ作成コマンドの GitHub ユーザー名を変更
- §4: CLAUDE.md テンプレートをプロジェクト構造に合わせて調整
- §7: 自分の分野に合ったディレクトリ命名に変更
- §9: ユースケースに応じて安全規則を追加・削除
- `setup.sh`: リポ clone の GitHub ユーザー名を変更

## ライセンス

MIT

# リポジトリ規約

最終更新: 2026-04-07

> **正本は `~/Claude/claude-config/CONVENTIONS.md`。** `~/Claude/CONVENTIONS.md` は symlink。
> 編集後は `cd ~/Claude/claude-config && git add -A && git commit && git push`。
> **規約を追加・修正する前に** [docs/convention-design-principles.md](docs/convention-design-principles.md) を読むこと（配置原則・重複回避・追加判断基準）。
> ドメイン固有規約は `conventions/` に分離: [shared-repo.md](conventions/shared-repo.md), [latex.md](conventions/latex.md), [mcp.md](conventions/mcp.md), [research-email.md](conventions/research-email.md), [collaborators.md](conventions/collaborators.md), [substack.md](conventions/substack.md), [scheduled-tasks.md](conventions/scheduled-tasks.md), [shell-env.md](conventions/shell-env.md), [dropbox-refs.md](conventions/dropbox-refs.md)
>
> **パスの記述規則:** CLAUDE.md・SESSION.md 等でローカルパスを記述する際は `~` で表記（例: `~/Dropbox/...`）。`/Users/odakin/` のようなユーザー固有の絶対パスは共同編集者の環境で壊れるため使わない。

---

## 1. リポジトリ作成・同期

```bash
gh repo create <username>/<name> --private --description "<English description>" --clone
cd <name> && git branch -M main
git add . && git commit -m "Initial commit: <概要>" && git push -u origin main
```

description は英語。リポ一覧の正本は **`odakin-prefs/repos.md`**。新規作成前に既存リポを確認。

---

## 2. 必須ファイル

| ファイル | 役割 |
|---------|------|
| `CLAUDE.md` | 永続的指示書（構造・実行方法・復帰手順）。構造変更時のみ更新 |
| `SESSION.md` | 揮発的な現在状態（作業中タスク・直近の決定）。進行に応じて更新 |
| `DESIGN.md` | **決定した**設計判断とその理由（Why / 代替案 / トレードオフ / defer 判断）。判断が生じたら即記録。**未決定の探索は `EXPLORING.md`（任意）へ** |
| `.gitignore` | ビルド成果物・OS/エディタファイル・機密情報の除外。共有リポでは全パターン明記 |

CLAUDE.md は「どうやるか」、SESSION.md は「今どこにいるか」、DESIGN.md は「なぜそうしたか」。

### 任意ファイル

**`ARCHITECTURE.md`**（または `docs/ARCHITECTURE.md`）— コードの 30,000ft ナラティブ。レイヤ構成・主要概念・データフローを散文で書く。

- **作る基準:** コードリポで CLAUDE.md の構造説明が表 1 つに収まらず、ファイル名やクラス名から関係性が読み取れない場合（例: 物理/通信/UI が分離、非同期パイプライン、独自の概念モデル）
- **作らない:** LaTeX 論文・記事・データ運用・薄いスクリプト集など構造説明が CLAUDE.md に収まるリポ。ファイルツリーやクラス一覧だけになるなら不要
- **前例:** [LorentzArena/docs/ARCHITECTURE.ja.md](https://github.com/sogebu/LorentzArena/blob/main/docs/ARCHITECTURE.ja.md)

**`EXPLORING.md`** — 未決定の思考・代替案・option space の棚卸し

- **作る基準:** DESIGN.md が肥大化してきて（目安 400 行超）、かつ未決定の思考メモが複数同時進行しているとき。小さいリポや「決定しか書くことがない」リポでは不要
- **書くもの:** 決定前の代替案比較、候補の tradeoff 表、open questions、暫定方向（commit せずに「A が有力、B はこの理由で却下」程度の踏み込み）、pre-decision の設計思考
- **書かないもの:**
  - 決定したこと → DESIGN.md
  - defer 判断と un-defer トリガー → DESIGN.md（defer も決定の一種）
  - 現在の作業状態・未完了タスク → SESSION.md
- **lifecycle:** 探索が決定に結晶したら該当セクションを DESIGN.md に promote し、EXPLORING.md から削除する。陳腐化した選択肢も削る。ファイル全体が空になったら削除してよい
- **DESIGN.md との境界判別:** 迷ったら DESIGN.md に書く。EXPLORING.md は「完全に option space を広げている段階」専用。70% 決まっていて 30% 迷っている状態は DESIGN.md に「暫定決定（再検討トリガー: X）」として書く
- **根拠:** 決定（安定・長寿命）と探索（不安定・短寿命）を同じファイルに同居させると DESIGN.md の役割契約（「なぜそうしたか」）が弱まり、reader の signal-to-noise が下がる。詳細は `docs/convention-design-principles.md` §6

### 記録先の判別

| 情報の性質 | 書き先 |
|---|---|
| ユーザーの好み・フィードバック・外部サービスへの参照 | メモリ（マシンローカル） |
| 現在の作業状態・未完了タスク | SESSION.md |
| 永続的な仕様・構造・手順 | CLAUDE.md |
| **決定した**設計判断とその理由（defer 含む） | DESIGN.md |
| 未決定の探索・代替案比較・暫定方向 | EXPLORING.md（任意、なければ DESIGN.md にタグ付きで） |
| 全プロジェクト共通の規約 | CONVENTIONS.md |
| grep / git log で導出可能な事実 | 書かない |

**よくある間違い:**
- 進行状態をメモリに書く → SESSION.md に書くべき（リポに入り全端末で共有される）
- `~/Claude/` 内の別リポへのパスをメモリに書く → メモリは `~/.claude/` 配下でマシンローカル（git 同期されない）。cross-repo ポインタは CLAUDE.md 等の git 側に書く。メモリの reference 型は外部 SaaS (Linear, Grafana 等) への参照用

---

## 3. 自動更新プロトコル

**人間に言われなくても自動で行う。**

SESSION.md:
- **更新タイミング:** タスク完了・重要な判断・ファイル作成/大幅変更・エラー発生時。出力テキストは揮発する。
- **認識の転換点:** 方針変更・ユーザー決定・前提の修正では **その場で** SESSION.md に書く（後回しにすると autocompact で消失）。決定事項には **What**（具体的手順）・**Why**（代替案と棄却理由）・**How**（実装方法）を含める。
- **棚卸し（目安80行以内）:** 完了 `[x]` を除去、実装詳細は git log に委任、重複を排除、恒久的決定は CLAUDE.md に移動。
- **新セッションテスト:** セッション終了前に SESSION.md だけで What/Why/How が復元できるか検証。

MEMORY.md（目安150行以内）: 2週間以上未使用プロジェクトを除去、CONVENTIONS 昇格済みフィードバックを除去、解決済み案件を除去。

### push の粒度と障害対応

git の状態管理は 1 本の `PostToolUse` hook で機械的に支援する: `claude-config/hooks/git-state-nudge.sh`。Bash 実行ごとに動作し、現在の CWD が git リポなら以下 3 ケースを検査して警告を session context に注入する。clean / in-sync な repo では完全に silent (Claude Code の hook 実行 notification も出ない)。

- **直近 60 秒以内の commit が未 push** → §4 「コミット後は常に push」を機械的に思い出させる。意図的に stack している場合は無視してよい。1 つの commit につき 1 回だけ警告（同じ HEAD sha では再警告しない）
- **直近 4 時間以内に触っていない repo に入った時、それが dirty / ahead** → セッション base dir が repo でなく、サブ repo に `cd` した際の "stale state inheritance" を検出
- **同上で behind** → first-sighting 時には hook が `git fetch` (5s timeout) を 1 回だけ実行するため、remote の進捗が local より先行していれば警告される。divergence を放置して大きな変更を加えると、後の rebase で衝突しファイル破損のリスクがある

4 時間 window は cross-session で marker file (`$HOME/.claude/state/git-nudge/`) に永続化されるため、短時間の連続セッションで spam しない設計（厳密な per-session 検出ではない点に注意）。fetch は first-sighting 時のみで、subsequent calls は network なしで ~0.2s。

> **設計補足:** 以前は SessionStart hook (`session-git-check.sh`) が session 起動時に独立して fetch + 警告を行っていたが、Claude Code が hook 実行のたびに「セッションを初期化しました / セッションstartupでフックを実行しました」notification を出すため平常時にもノイズになっていた。そこで SessionStart を撤廃し、divergence 検出を `git-state-nudge.sh` の first-sighting 経路に統合した。失う機能は「Bash 実行前の divergence 警告」だけで、初 Bash で同等の警告が出る。

- **作業単位ごとの push を推奨。** まとまった単位 (1 件の処理完了、1 つの構造変更など) が終わるごとに commit + push すると、後で他の作業者と衝突したときの解決が楽になる。バッチ push する流儀の人は各自の判断で。ただし §4 の「コミット後は常に push」は必須で、その強制は hook が担う。
- **push 障害は即座に解決する。** rebase コンフリクト・認証エラー等を放置しない。大規模な diverge が判明した場合は、破壊的な `reset --hard` を実行する前に必ず `/tmp` などに現状をバックアップ。

### push 前チェック

1. SESSION.md 更新（長ければ棚卸し） 2. CLAUDE.md 更新（構造変更時のみ） 3. 4軸レビュー → commit → push。軽微な変更では 2-3 スキップ可。

| 軸 | 内容 |
|---|---|
| **整合性** | 変更ファイル間で数値・用語・参照先が一致しているか |
| **無矛盾性** | 既存ルール・テンプレートと矛盾していないか |
| **効率性** | 重複がないか。SESSION.md ~80行、MEMORY.md ~150行以内か |
| **安全性** | 個人情報・認証情報が公開リポに含まれていないか |

ユーザーが「**3軸チェック**」と言った場合は上表のうち **整合性・無矛盾性・効率性** のみを指す（安全性は除外）。「4軸チェック」は全 4 軸。

**リポでの作業開始手順（全場面共通）:** CLAUDE.md → SESSION.md（要対応を確認）→ 作業開始。autocompact 復帰・scheduled task・SKILL 実行・手動作業すべてに適用。親ディレクトリで作業中にタスクが既存リポの管轄だと判明した場合も同様（MEMORY.md リポ一覧で特定 → そのリポの CLAUDE.md を読む）。「簡単なタスク」も例外ではない。CLAUDE.md 内のポインタ（「正本は X」「詳細は Y 参照」）は必ず辿る

---

## 4. Git 規約

- ブランチ `main` 統一。コミットメッセージは英語・動詞始まりを推奨（命令形: `Add X`, `Fix Y`, `Update Z`）。絶対ルールではなく、名詞句始まりや過去形でも意味が通れば許容
- **コミット後は常に push。** 複数リモートがあれば全リモートに push。`git-state-nudge.sh` hook (§3) が直近 60 秒以内の未 push commit を機械的に検出して警告するため、Claude はこの警告を見たら次の Bash で push を実行すること
- セッション終了時は未コミット変更があれば commit + push
- ファイル名にバージョン番号をつけない

---

## 5. 安全規則（絶対厳守）

1. 他人のファイル削除前に確認しユーザーに提示
2. 既存データ削除時はリネーム (`mv old old.bak`) を優先提案
3. force push 禁止（必要なら `--force-with-lease`）
4. 機密情報はコミットしない。同じファイルを複数リポに置かない
5. 破壊的操作は事前にユーザー確認。自分のリポのみ操作
   - **OS のプライバシー・セキュリティ設定を変更するコマンドの禁止**。変更はユーザーが手動で行う。macOS 固有の deny ルール詳細は [conventions/shell-env.md](conventions/shell-env.md) 参照
6. **機密データを含むリポの公開禁止**: 個人情報・金融情報・認証情報を含む private リポは絶対に public にしない。該当リポの CLAUDE.md 冒頭に `⚠️ このリポは private 必須` 警告を入れること。新規リポ作成時に機密データを扱う場合は同様の警告を追加し、暗号化手順がある場合はそれに従う（ない場合は [docs/git-crypt-guide.md](docs/git-crypt-guide.md) を参照）
7. **MCP 操作前のアカウント確認**: Gmail・Calendar 等の MCP ツールを初めて使う前に `get_profile` 等で接続先アカウントを確認すること。複数アカウントが接続されているのが常態。送信元・操作先の取り違えは不可逆。詳細は [conventions/mcp.md](conventions/mcp.md)

---

## 6. 網羅性の検証

「全部」を主張する場合、列挙の前に機械的な検証基準を定め、列挙後に照合する。
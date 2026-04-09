---
status: active
created: 2026-04-09
lifetime: transient — 全セッション完了後にこのファイルは削除する
---

# 公開リポ leak 防止 実装計画

> **一時文書**。実装完了時点でこのファイルは削除する。最終的な設計判断は
> `DESIGN.md` の「公開リポ leak 防止」セクションに、事故記録は
> `odakin-prefs/leak-incidents.md` に、将来課題は
> `odakin-prefs/next-steps.md` にそれぞれ残す。この plan.md はあくまで
> 「実装中のカーソル + step の依存関係」を保持するための脚立。

## 0. ゼロ再開用サマリ (autocompact/他 Mac/日数中断耐性)

**動機**: 2026-04-09 に LorentzArena (public) で組織環境を暗示する表現
(`<wifi_term>` 系) が 5 ファイル 16 行に累積していたのをユーザー指摘で
発見、`ae25604` で一般化。Claude 側は drafting 中も push 前も catch
していなかった。指示層 (`odakin-prefs/work-network.md`) では reliably
トリガーが引けないと判明したので、`memory-guard.sh` / `git-state-nudge.sh`
と同じ「指示 → hook 化」の pattern upgrade を適用する。

**設計の核 (3 行)**:
- **PreToolUse hook**: Tier A 構造制約 regex のみ (email / abs path /
  IPv4 / token prefix)。literal blocklist は乗せない — `sensitive-repo-patterns.ja.md §3-3`
  の純粋適用
- **pre-commit hook**: Tier A regex + `odakin-prefs/sensitive-terms.txt`
  の ephemeral load (存在時のみ、stage 済み diff のみ scan)。script
  本体には literal を埋め込まない構造分離で §3-3 の批判 (b)
  「blacklist 自体が leak 源」を回避しつつ literal catch を commit
  gate に集約
- **audit**: `gh repo list --visibility public` + marker file の突合
  + Tier A + sensitive-terms.txt ephemeral load で全 public repo を
  定期 sweep。受容 leak は `leak-incidents.md` に記録

**判定単位**:
- public/private の判定は **`<repo>/.claude/public-repo.marker` 一本**。
  hook の日常 fast path はこれだけ見る。`gh repo list` との突合は
  `setup.sh` と `audit-public-repos.sh` の「遡及検出」で補う
- marker 内容は汎用英語メタデータのみ (固有名詞なし)、それ自体が leak
  しない構造

**参照必須ドキュメント** (実装前に必ず開く):
- `claude-config/docs/sensitive-repo-patterns.ja.md` — 設計思想の出所。
  特に **§3-3 "構造制約の設計思想"**, §5-1 "Forcing functions >
  discipline", §5-2 "新規ルールと既存違反の同日 sweep"
- `claude-config/docs/convention-design-principles.md` — §1 配置原則,
  §2 「定義は1箇所」, §3 「規約追加は最終手段」(過剰規約回避)
- `claude-config/CONVENTIONS.md` §5 item 6 — 機密データを含むリポの
  公開禁止 (対応関係: public repo 側の安全規則と表裏)
- `claude-config/hooks/memory-guard.sh` — `PreToolUse Edit|Write` の
  高速パス + `permissionDecision=ask` パターンのテンプレ
- `claude-config/hooks/git-state-nudge.sh` — state marker + fast path
  + per-repo hash の書き方テンプレ
- `odakin-prefs/work-discipline.md` — 承認後の実装フェーズでの
  TodoWrite 起動 / `ls -A` 模倣 / cross-machine ゲートの 3 規律
- `odakin-prefs/work-network.md` — 段階 4 で placeholder 化する対象
  (組織名 literal を sensitive-terms.txt へ分離)
- `odakin-prefs/push-workflow.md` — commit/push 粒度、divergence
  interpretation、`git-state-nudge.sh` 警告対応

**判断履歴の主要分岐点** (なぜこの設計なのか思い出せない時用):
1. 初案 (3 tier blacklist: deny / ask / hint) → `sensitive-repo-patterns.ja.md §3-3`
   と直接衝突 → 棄却
2. pure 3-3 (Tier A regex のみ、literal は一切 hook に乗せない) →
   LorentzArena 型事例 (間接 context leak) を catch できない
3. **採用案 (中間解)**: PreToolUse は Tier A のみ、pre-commit では
   `sensitive-terms.txt` を **ephemeral load** (script 本体に literal を
   埋め込まない)。§3-3 の最重要批判 (b) は構造的に回避、(a)(c)
   「メンテ要」「新固有名詞追随不可」は運用で許容
4. attention banner (各 public repo CLAUDE.md 冒頭への忌避語リスト)
   → user 判断で **不採用**。public repo に個人 attention layer を
   乗せない方針
5. odakin-prefs 全体の git-crypt 化 → **不採用**。§3-3 の思想は
   「暗号化で守る」ではなく「漏らせないものを平文側に置かない」(情報
   配置の分離)。段階 1 (work-network.md だけを分離) で十分、段階 2-3
   は `next-steps.md` に切り出し
6. 既存 leak の force push → **原則しない**。`leak-incidents.md` に
   受容記録。例外は「認証情報が入った場合」「push 1 時間以内の
   個人識別情報」のみ

## 1. 現在位置カーソル

- [x] **セッション 1** (planning): 本 plan.md + DESIGN.md 追記 +
  leak-incidents.md + next-steps.md + CLAUDE.md 必須テーブル編集 +
  commit/push — **2026-04-09 実施**
- [ ] **セッション 2** (hook + marker): `public-leak-guard.sh` 実装 +
  marker file 設置 (LorentzArena + claude-config) + settings.json 登録
  + 動作確認
- [ ] **セッション 3** (pre-commit + installer): `public-precommit-runner.sh`
  + `install-public-precommit.sh` + LorentzArena/claude-config で
  install (sensitive-terms.txt は未配置で空 load fallback の動作確認)
- [ ] **セッション 4** (情報分離): Dropbox 正本 → `sensitive-terms.txt`
  symlink + `odakin-prefs/.gitignore` 追加 + `work-network.md` の
  組織名 literal を placeholder へ置換 + pre-commit hook の literal
  catch 動作確認 (LorentzArena で `<wifi_term>` を fake edit → commit
  reject を確認)
- [ ] **セッション 5** (audit + 全 repo 展開 + setup.sh): `audit-public-repos.sh`
  実装 + 初回 sweep + 発見 leak の修正/受容判断 + 他 public repo
  (zenn-articles, devto-articles, webGL-test, etc.) への marker +
  pre-commit install + `setup.sh` に hook installer layer 追加 + 本
  plan.md 削除 + DESIGN.md 最終状態更新

**autocompact 後の再開手順**:
1. 本ファイル (plan.md) §0 を読む (3 行の設計核 + 参照必須 doc を把握)
2. §1 のチェックリストで現在位置を確認
3. 対応するセッション節 (§2-§6) を読む
4. 記載の completion criteria を 1 つずつ潰す
5. セッション完了時に §1 を update + commit

## 2. セッション 2 — hook + marker

### 目的
PreToolUse Edit/Write で Tier A 構造制約を強制する。literal blocklist
はまだ乗せない (§3-3 純粋)。この段階ではメール / 絶対パス / IPv4 /
token prefix leak を 100% catch する状態を作る。

### 依存
- セッション 1 完了 (plan.md / DESIGN.md の設計決定が存在)
- `memory-guard.sh` と `git-state-nudge.sh` のパターン流用 (fast path
  + jq による tool_input 抽出 + `permissionDecision` 出力形式)

### Steps

1. **`claude-config/hooks/public-leak-guard.sh` 実装**:
   - stdin (`tool_input.file_path`, `tool_input.new_string` または
     `content`) を jq で抽出
   - file_path から git repo root を特定
   - `$REPO_ROOT/.claude/public-repo.marker` が存在しなければ `exit 0`
     (fast path)
   - 4 種の regex check を順次実行:
     - `email`: `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}` —
       allowlist: `noreply@anthropic\.com`, `noreply@github\.com`,
       `support@github\.com` (必要なら追加)
     - `abs_path`: `/Users/[a-z][a-z0-9_-]*` — 個人 absolute path の
       一般形
     - `ipv4`: `\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b` — (allowlist: `0.0.0.0`,
       `127.0.0.1`, `255.255.255.255` 等の汎用例示)
     - `token_prefix`: `(ghp_|github_pat_|sk-[A-Za-z0-9]{20,})` — GitHub
       PAT / OpenAI key の prefix
   - hit した場合は `permissionDecision=deny` + 該当 pattern 名 + hit
     した具体行を stderr に出力
   - hit なしなら `exit 0` silent

2. **`.claude/public-repo.marker` の content template**:
   ```
   # claude-public-repo-marker
   # This repository is publicly accessible.
   # Leak prevention hooks enforce structural checks on Edit/Write and
   # at pre-commit time. See:
   #   - claude-config/hooks/public-leak-guard.sh
   #   - claude-config/scripts/public-precommit-runner.sh (phase 2)
   #   - claude-config/scripts/audit-public-repos.sh (phase 3)
   ```
   汎用英語、固有名詞なし、audit の `diff` で改変検出にも使う。

3. **marker を設置**: LorentzArena と claude-config に上記 content で
   commit。他 public repo (zenn-articles, devto-articles, webGL-test,
   arxiv-digest, mhlw-ec-pharmacy-finder など `gh repo list --visibility public`
   で列挙される全 repo) への設置はセッション 5 に回す (hook が動く
   ことを 2 repo で先に確認したいため)

4. **`~/.claude/settings.json` への登録**: 既存の
   `PreToolUse Edit|Write` matcher に `public-leak-guard.sh` を追加
   (memory-guard.sh と並列)。`setup.sh` 側の merge ロジックの更新は
   セッション 5 に回し、この時点では手で settings.json を編集する

5. **動作確認**:
   - LorentzArena 内で `README.md` の末尾に fake email を書く Edit
     → deny されることを確認
   - claude-config 内で fake `/Users/someone/` を書く → deny
   - marker なしの repo (odakin-prefs 等) で同じ操作 → 素通し
   - 正当な内容 (coordinate 等) が false positive にならないことを確認

### Completion criteria (セッション 2)
- [ ] `public-leak-guard.sh` が commit されている
- [ ] `.claude/public-repo.marker` が LorentzArena と claude-config に
  存在し、両 repo で動作確認済み
- [ ] `~/.claude/settings.json` に hook 登録済み (手編集で OK)
- [ ] marker なし repo で素通しすることを確認
- [ ] 本 plan.md §1 のカーソルが「セッション 3」に進んでいる

## 3. セッション 3 — pre-commit + installer (sensitive-terms.txt は未配置)

### 目的
pre-commit gate を構築する。中身は Tier A regex だけで、
`sensitive-terms.txt` はまだ作らない。この段階で **空の ephemeral
load が安全に no-op する** ことを確認する (fallback の健全性)。

### 依存
- セッション 2 完了 (marker + hook が動いていること)
- `sensitive-repo-patterns.ja.md §3-3` の hook 構造を参考 (size cap
  / regex / exit code)

### Steps

1. **`claude-config/scripts/public-precommit-runner.sh` 実装**:
   - git 側から呼ばれる想定 (`.git/hooks/pre-commit` 経由)
   - `git diff --cached --name-only` で staged files 取得
   - 各 file の `git diff --cached -U0` を取り、`+` で始まる
     added-line のみ抽出 (既存 line への regex 誤爆を防ぐ)
   - Tier A regex (public-leak-guard.sh と完全に同じ 4 種) を適用
   - `[ -f $HOME/Claude/odakin-prefs/sensitive-terms.txt ]` ならその
     file を `grep -F -f` に渡して ephemeral literal check (段階 4
     で中身が入るが、今は空でも動くことを確認)
   - hit があれば `exit 1` + stderr に詳細。なければ `exit 0`
   - `--no-verify` で bypass 可能 (git 標準)。docstring でこれは
     **意図的な operational escape hatch** と明記

2. **`claude-config/scripts/install-public-precommit.sh` 実装**:
   - 引数: 対象 repo path (または無指定で cwd)
   - 対象 repo に `.claude/public-repo.marker` があることを確認
     (marker なしなら install しない)
   - `$REPO/.git/hooks/pre-commit` に以下の 1 行 stub を書き込む:
     ```bash
     #!/bin/bash
     exec "$HOME/Claude/claude-config/scripts/public-precommit-runner.sh" "$@"
     ```
   - chmod +x
   - 既存の pre-commit があれば backup (`.pre-commit.bak-<date>`) して
     上書き。backup があれば warn

3. **LorentzArena と claude-config で install 実行**

4. **動作確認**:
   - LorentzArena で fake email を含む commit を試行 → reject
   - `sensitive-terms.txt` が存在しない状態での空 load が safe に
     skip されることを確認 (セッション 4 の前提)
   - `--no-verify` で bypass できることを確認 (escape hatch の動作確認)

### Completion criteria (セッション 3)
- [ ] `public-precommit-runner.sh` と `install-public-precommit.sh` が
  commit されている
- [ ] LorentzArena と claude-config の `.git/hooks/pre-commit` に stub
  が入っている
- [ ] email を含む fake commit が reject されることを確認
- [ ] sensitive-terms.txt 不在での空 load が no-op であることを確認
- [ ] `--no-verify` で bypass できることを確認
- [ ] plan.md §1 カーソルがセッション 4 に進行

## 4. セッション 4 — 情報分離 (sensitive-terms.txt + work-network.md placeholder 化)

### 目的
Dropbox を正本とする `sensitive-terms.txt` を作成し、`odakin-prefs/`
には symlink 経由で参照させる。`work-network.md` の組織名 literal
を placeholder に置換して、odakin-prefs が万一 leak しても sensitive
literal が git に乗っていない状態を作る。

### 依存
- セッション 3 完了 (pre-commit が空 load で動いていること)
- Dropbox root は既存の `claude-config/scripts/dropbox-root.sh` で
  OS-agnostic に resolve 可能

### Steps

1. **Dropbox に正本配置**:
   - `<Dropbox>/claude/sensitive-terms.txt` (path は dropbox-refs.md
     の命名規則に合わせる) を作成
   - 中身は 1 行 1 term の plain text。category コメントは **書かない**
     (`sensitive-repo-patterns.ja.md §2-3` に従いコメントも leak 源)
   - 初期 entries:
     - 組織名・略称系 (`odakin-prefs/work-network.md` の表から抽出。
       具体値は本 plan.md には書かない)
     - LorentzArena 事例で発覚した間接 context leak 表現の派生語
       (具体語は sensitive-terms.txt 内部にのみ記載、本 plan.md には
       含めない — それ自体が meta-leak になるため)
     - 他は段階 2 (next-steps.md) で追加

2. **symlink 作成**:
   ```bash
   ln -s "$(~/Claude/claude-config/scripts/dropbox-root.sh)/claude/sensitive-terms.txt" \
         ~/Claude/odakin-prefs/sensitive-terms.txt
   ```

3. **`odakin-prefs/.gitignore` に追加**:
   ```
   # sensitive literal は machine-local + Dropbox 正本で管理
   # (claude-config/docs/leak-prevention-plan.md §4)
   sensitive-terms.txt
   ```

4. **`odakin-prefs/work-network.md` の placeholder 化**:
   - 組織名 literal を `<workplace>` 等の placeholder に置換
   - 冒頭に「sensitive literal は `sensitive-terms.txt` に分離。本文は
     placeholder で読むこと」という注記
   - 散文説明 (なぜ一般化するか) は残す — 思考フレームを持つための
     情報は必要
   - sensitive-terms.txt を参照する旨の pointer を追加 (gitignore 側の
     machine-local fallback の挙動を説明)

5. **動作確認**:
   - LorentzArena で `<wifi_term>` に相当する literal を docs に追加
     して commit 試行 → pre-commit が literal を検出して reject
   - `--no-verify` で bypass せず、literal を一般化する形で書き直す
   - 書き直した内容で commit 成功することを確認

### Completion criteria (セッション 4)
- [ ] Dropbox 正本の `sensitive-terms.txt` が作成されている
- [ ] `odakin-prefs/sensitive-terms.txt` が symlink として存在
- [ ] `.gitignore` に追加され `git status` で無視されていることを確認
- [ ] `work-network.md` の組織名 literal が placeholder 化されている
- [ ] LorentzArena で literal を含む commit が reject されることを確認
- [ ] plan.md §1 カーソルがセッション 5 に進行

## 5. セッション 5 — audit + 全 repo 展開 + setup.sh + plan.md 削除

### 目的
`audit-public-repos.sh` を実装して既存 leak を洗い出す。全 public repo
に marker + pre-commit を展開する。`setup.sh` に hook installer layer
を追加して新 Mac でも自動設置される状態を作る。最後に本 plan.md を
削除し、最終状態を DESIGN.md に収斂させる。

### 依存
- セッション 4 完了 (sensitive-terms.txt が実データで動いている)
- `setup.sh` の既存 layer 構造 (CLAUDE.md 参照) と整合する新 layer 番号

### Steps

1. **`claude-config/scripts/audit-public-repos.sh` 実装**:
   - `gh repo list --visibility public --limit 200 --json nameWithOwner`
     で public repo 一覧取得
   - `~/Claude/<repo>/` が存在する repo のみを対象にする
     (他 org の public repo は scope 外)
   - 各対象 repo で:
     - marker 有無を check (missing は warn)
     - `git grep -nE "$TIER_A_REGEX"` で Tier A 違反を列挙
     - `[ -f sensitive-terms.txt ]` なら `git grep -nF -f
       sensitive-terms.txt` で literal 違反を列挙
   - 結果を markdown report として `/tmp/public-leak-audit-<date>.md`
     に出力 (odakin-prefs には追記しない — noise 回避)
   - scheduled-task から呼ぶ想定 (週次)、だが本セッションでは手動
     初回実行

2. **初回 audit 実行 → 発見 leak の処理**:
   - Tier A 違反 (regex-catchable) があれば **全件修正** (hook 設置後
     なので新規 leak は発生しない前提、既存分だけが対象)
   - literal 違反は判断: 修正 / 受容 / 素材移動 の 3 択
   - 受容した leak は `odakin-prefs/leak-incidents.md` に entry 追加
   - 修正した leak は commit、leak-incidents.md には簡潔に記録

3. **全 public repo への marker + pre-commit 展開**:
   - `gh repo list --visibility public --limit 200` で列挙
   - 各 repo に対して:
     - `~/Claude/<repo>/.claude/public-repo.marker` を作成 + commit + push
     - `install-public-precommit.sh` を実行して pre-commit stub 配置
   - 対象は bulk 展開できるので script 化しても良い

4. **`claude-config/setup.sh` に hook installer layer 追加**:
   - 既存 layer 番号に続けて新 layer を追加 (layer 12 想定)
   - 機能:
     - marker が設置済みの全 repo に対して `install-public-precommit.sh`
       を実行
     - `gh repo list --visibility public` と marker の突合、missing
       marker を警告 (自動設置はしない — ユーザー確認必須)
     - settings.json に `public-leak-guard.sh` の hook 登録を merge
   - 冪等性を持たせる (既に install 済みなら no-op)

5. **scheduled-task 登録**: `mcp__scheduled-tasks__create_scheduled_task`
   で週次 audit を登録
   - prompt: audit-public-repos.sh を実行 + 結果を読んで leak-incidents.md
     に追記すべきものがあれば user に提示
   - cron: 週 1 回、off-minute (例: `17 9 * * 1`)

6. **最終整理**:
   - `claude-config/DESIGN.md` の「公開リポ leak 防止」セクションを
     「最終状態」に更新 (セッション 1 時点では「実装計画あり」状態、
     完了時に「実装済み、hook/script 場所、設計判断」に差し替え)
   - `claude-config/SESSION.md` の残タスクから本件を削除
   - **本 plan.md を削除**
   - commit + push (claude-config と必要なら他 repo 全件)

### Completion criteria (セッション 5)
- [ ] `audit-public-repos.sh` が commit されている
- [ ] 初回 audit 実行済み、発見 leak の処理完了
- [ ] 全 public repo に marker + pre-commit 展開済み
- [ ] `setup.sh` に hook installer layer 追加済み、新 Mac シミュレーション
  で idempotent 動作確認
- [ ] scheduled-task 登録済み
- [ ] DESIGN.md が最終状態に更新
- [ ] **本 plan.md 削除済み**
- [ ] plan.md §1 の全チェックボックスが埋まっている (削除前の最終確認)

## 6. リスクと mitigations

| リスク | 発生時期 | 対処 |
|---|---|---|
| Tier A regex の false positive (正当な email / coord が deny) | セッション 2-3 | allowlist 追加 + docstring で bypass 手順明示 |
| pre-commit が重い (大 repo で grep 遅い) | セッション 3 | staged diff のみ scan で抑制。full repo scan はしない |
| marker 付け忘れで新 public repo が素通し | 恒常 | audit script の missing marker 警告 + setup.sh での検出 |
| sensitive-terms.txt の Dropbox sync 遅延 | セッション 4 以降 | 新 Mac で初回 unlock 時に手動確認 (symlink 切れは即発覚) |
| pre-commit が `--no-verify` で bypass され続ける | 恒常 | `leak-incidents.md` に bypass 事例を記録、3 回で forcing function 強化を検討 (`sensitive-repo-patterns.ja.md §5-1`) |
| 段階 1 だけでは odakin-prefs の他 sensitive (repos.md / collaborators / user-profile) が露出したまま | 恒常 | `next-steps.md` に段階 2-3 を issue 化。un-defer トリガー設定済み |
| 古い git log に残る leak は force push しない方針 | 恒常 | 受容、`leak-incidents.md` に記録、将来の新 content で素材置換 |

## 7. セッション跨ぎの整合性チェック (各セッション終了時)

1. `claude-config/` と `odakin-prefs/` が両方 clean + in-sync であること
2. plan.md §1 カーソルが正しい位置に進んでいること
3. 当該セッションの completion criteria が全て埋まっていること
4. 次セッションの「依存」で要求される前提が満たされていること
5. `work-discipline.md` の 3 規律 (ls -A / TodoWrite / cross-machine
   ゲート) に違反していないこと

## 8. 完了判定と post-mortem

全 5 セッション完了後:
1. `leak-incidents.md` に最終 audit 結果を転記
2. 実装全体の 4 軸レビュー (整合性 / 無矛盾性 / 効率性 / 安全性) を
   実施、発見事項は DESIGN.md に追記
3. 本 plan.md を削除 (`git rm`)
4. `SESSION.md` から本件を削除
5. 3 ヶ月後に再発 leak の有無を確認 — なければ設計成功、1 件以上
   あれば `next-steps.md` で forcing function 強化を検討

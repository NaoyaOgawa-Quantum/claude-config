# SESSION — claude-config

## 現在の状態

**2026-04-28**: `public-precommit-runner.sh` に optional な repo-local extension hook chain (`.claude/pre-commit-extra.sh`) を追加。stub の冪等性を保ったまま repo 固有の commit 規律 (placeholder 検出 / docs↔SESSION.md 同期警告等) を chain できる。mhlw-ec-pharmacy-finder で動作確認 (旧 inline hook の guard を extension に移設、外側 stub と差し替え)。5 commit (`590ab9f` chain + DESIGN §2026-04-28 追補 / `8efeaac` gitignore_global で `!.claude/pre-commit-extra.sh` / `25412e7` 作成 guide 5 項追記 / `7b6a112` exec→call で trap leak 修復 / 本 commit runner header doc を call+exit に同期 + 本 SESSION 記載)。詳細は DESIGN.md §2026-04-28 追補。

**2026-04-23**: ある private collaborative git-crypt リポでの復号失敗事故 (個人層 satellite doc の placeholder 誤展開で file-not-found に陥った) を起点に、再発防止の規約・ガイド・テンプレ整備 4 commit (`e87d3df` / `ee84741` / `4ca20c3` / `46e2fb6`) 完遂。docs/git-crypt-guide.ja.md §共有リポでの自動復元 新設、templates/shared-project に SETUP.md.template + 既存バグ (README.md.template 不在) 修復、CONVENTIONS.md + conventions/shared-repo.md に SETUP.md パターン正式採用 + 4軸 audit drift 修復。

**2026-04-21**: onboarding 補強 (commit `58a7696`) と §8 memory policy 整合 3 段 (`3a159c2` / `9d4ac3d` / `f1d026a`) 完遂。auto-push env var、leak 防止システム、README reorg、§7 retroactive reorg 等の過去セッション完了事項は git log と `DESIGN.md` 各 entry を参照。

## 今セッションの変更 (2026-04-23): git-crypt 復号失敗 → 再発防止の体系化

### 経緯

ある private collaborative git-crypt リポの復号で、個人層 satellite doc にあった placeholder (例: `<...>`) を「空に展開」と誤読 → file-not-found → 5 段アンチパターン (read 優先順位逆転 / placeholder 誤展開 / tool 再実装 / 事前確認なし / 事後確認なし) で迷走した事故。手動 openssl の path 依存 + canonical (setup.sh + `.claude/git-crypt-backup`) 未利用 + 事前/事後確認なし、の組合せが重なった。

### claude-config 側の整備 4 commit

- **`e87d3df`** `docs/git-crypt-guide.ja.md` に §共有リポでの自動復元 (`.claude/git-crypt-backup` 経路) 新設。setup.sh Step 5b-pre が `find` で path 非依存に鍵を発見・復号・unlock する機構を canonical recovery として記述、共同編集者向け運用 + 公開しても安全な記述例も併記
- **`ee84741`** `templates/shared-project/SETUP.md.template` 新設 (5 段防御込み: 反パターン警告 / 推奨 setup.sh 経路 / 手動 fallback Step 0 事前確認 + Step 2 事後確認) + 既存 README.md.template 不在バグ修復 + CLAUDE.md.template の git-crypt 節を「SETUP.md への薄いポインタ + 反パターン警告のみ」に refactor (auto-load コスト原則を新規リポにも継承)
- **`4ca20c3`** 規約整備: CONVENTIONS.md 動的 docs 表に SETUP.md 追加 + §README の流儀禁忌を SETUP.md exception 込みに refinement、conventions/shared-repo.md §共有 git-crypt 鍵パターンを「個人 export-key 配布」古手順から「openssl 暗号化 backup + setup.sh 自動復元」canonical 経路に書き換え + §共同編集者向けの SETUP.md 新節
- **`46e2fb6`** 4軸 audit で検出した整合性 drift 2 件修復: CONVENTIONS の section reference 「§「共同編集者向け SETUP.md」」→「§「共同編集者向けの SETUP.md」」(の 1 文字差で grep miss)、shared-repo.md + SETUP.md.template の「末尾の事故事例」reference を実 heading 「共同編集者向け運用」に整合

### LESSON candidates

1. **placeholder 誤展開の構造的リスク**: `<...>` のような placeholder を中継 doc に置くと、Claude が prompt-time に推測展開して誤った literal を投げる事故が起きる。Canonical doc には literal で書く、または `find` で path 非依存にする機構 (今回の setup.sh Step 5b-pre) を提供する
2. **CLAUDE.md auto-load コストの新分類**: 共同編集者 onboarding walkthrough は CLAUDE.md (auto-load) ではなく SETUP.md (cold reference) に置く分離原則を確立。同一原則 (auto-load コスト) は次回他の cold-content (incident report 等) を新設するときも適用候補
3. **テンプレ整合性 audit の規律化**: templates/ に新規ファイル追加時、参照元 (CONVENTIONS / conventions/) との同期を 1 commit 内で揃える ([commit ee84741] と [commit 4ca20c3] の関係)、cross-reference は実 heading と grep-match させる ([commit 46e2fb6] で検出した drift)

## 今セッションの変更 (2026-04-21): onboarding 補強 + §8 memory policy 整合 3 段

### 200K コンテキストユーザ向け onboarding 補強 (commit `58a7696`)

(a) `templates/root-CLAUDE.md.default` に CONVENTIONS.md の 4 読み込みトリガー (リポ作業開始 / commit+push 前 / 新規リポ / 記録先判別) を追加、(b) `README.md`/`.ja.md` に「Context budget」節新設 (§10.7 既存閾値 50 KB / 100 KB を流用、invent せず)、(c) `docs/usage-tips.md`/`.ja.md` に §8「CLAUDE.md chain in sub-projects」tip 昇格。EN/JA parity、正本 CONVENTIONS.md は touch せず。

### §8 memory policy 整合 3 段 (commits `3a159c2` / `9d4ac3d` / `f1d026a`)

2026-04-17 §8 方針変更 (memory-guard `ask`→`deny` + `<!-- machine-local: -->` escape hatch) の波及漏れを 3 段で fix:

- **`3a159c2`** usage-tips Tip 6 を「memory に feedback を書く」→「conventions と hook に投資する」に inversion（symptom-level fix）
- **`9d4ac3d`** CONVENTIONS.md §2「記録先判別」table 1 行を 3 行に split (machine-local 事実・参照 / 恒久的好み・身元 / 再発防止 feedback)、§3 MEMORY.md 運用行と 4 軸 efficiency check の「MEMORY.md 150 行以内」を「index-only (§8.7)」に（authoritative source fix）
- **`f1d026a`** DESIGN.md hooks table + CLAUDE.md 構造ツリー + personal-layer CLAUDE.md template の hook description を実装 (deny + escape hatch) に揃える。特に `memory-guard-bash.sh`「警告のみ」は事実と逆（実装は deny）だった

**LESSON candidates** (DESIGN.md or principles.md への昇格を次回判断):

1. self-contradiction 修正時は symptom-level fix の前に `grep -rn <矛盾キーワード>` で upstream source を特定。spawn task prompt の scope を symptom に限定すると agent は upstream source を触れない
2. hook 動作変更 (`ask`→`deny` 等) と description の同期は同一 commit で揃える。source-of-truth (hook 実装) と description (DESIGN/CLAUDE.md/template) の drift は機械チェック困難

## Open items（forward-looking）

- [ ] **dropbox-refs.md の narrative 量監視** — 類似 narrative style の convention が他に波及したら系統 pattern として review
- [ ] **LorentzArena 2+1/CLAUDE.md ゲームパラメータ表の委譲は anti-value** (再訪禁止) — 再度検討しそうになったら `docs/convention-design-principles.md` §10.8 削除提案の self-correction 事例を先に読む
- [ ] **RUNBOOK 系ファイルの実例運用後再検討** — トリガー: いずれかのリポで CLAUDE.md からランブック切り出しの具体ニーズが出た時。詳細は DESIGN.md「RUNBOOK 系ファイル」
- [ ] **規約 rollout 原則の一般化** — case 2 発生 (RUNBOOK 導入 or 他 content-reorganization 系) で principles §7 新設昇格を再判断。1 データポイントでの formalize は YAGNI で defer 中
- [ ] **principles.md 昇格候補 4 件の再判定** — Narrower-but-active / Generator owns commit / Event-driven vs time-driven safety net / Multi-commit workflow checkpoint。un-defer トリガーは DESIGN.md 末尾「検討事項: principles.md への昇格候補」。最 strong は Event-driven vs time-driven (既に対比表あり)、最新で 1 データポイントしかないが緊急性が高いのは Multi-commit workflow checkpoint
- [ ] **CONVENTIONS.md §2 density audit** — un-defer トリガー: 100 行 or 15 KB 到達時に density check。現状 177 行 / 19 KB で trigger 発火済、次回セッションで `grep` 頻度が低い section の T1/T2 移動を検討
- [ ] **外向け発信候補** — 詳細メモは個人層 `odakin-prefs/blog-ideas.md` 参照（public 側には具体内容を置かない方針）

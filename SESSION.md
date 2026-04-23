# SESSION — claude-config

## 現在の状態

**2026-04-21**: onboarding 補強 (commit `58a7696`) と §8 memory policy 整合 3 段 (`3a159c2` / `9d4ac3d` / `f1d026a`) 完遂。auto-push env var、leak 防止システム、README reorg、§7 retroactive reorg 等の過去セッション完了事項は git log と `DESIGN.md` 各 entry を参照。

## 今セッションの変更（2026-04-21）

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

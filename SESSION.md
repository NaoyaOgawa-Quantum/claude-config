# SESSION — claude-config

## 現在の状態
**完了**: 公開リポ leak 防止システム全 5 セッション実装完了 (2026-04-09〜10)。Tier A regex hook + pre-commit Tier B literal check + audit + marker 12 repo 展開 + setup.sh Step 8 追加 + 週次 scheduled-task 登録。

**2026-04-14 追加**: `git-state-nudge.sh` の case (2)「commit 直後で AHEAD>0 / BEHIND=0」分岐に **opt-in auto-push** を追加。`CLAUDE_GIT_AUTO_PUSH=1` が環境変数で設定されている場合のみ hook 自身が `git push` を実行する。default は従来通り nudge のみ (claude-config は public で他ユーザーの流儀を強制しないため)。20s timeout で credential prompt / 固まりを guard。failure 時は `AUTO-PUSH FAILED` で push 出力を表示するので Claude/ユーザーが手動 resolve 可。詳細は odakin-prefs/push-workflow.md と odakin-prefs/shell-env.md。

## 今セッションの変更（2026-04-09〜10）

### 公開リポ leak 防止 — 設計・実装・全 repo 展開

**契機**: LorentzArena (public) で組織環境を暗示する間接表現が 5 ファイル 16 行に累積していた (commit `ae25604` で修正済み)。Claude 側は catch できていなかった。

**設計**: `sensitive-repo-patterns.ja.md §3-3` 優先で構造制約 hook と情報配置分離の 2 本柱。5 セッションで段階実装。詳細は DESIGN.md §公開リポ leak 防止。

**成果物 (主要)**:
- `hooks/public-leak-guard.sh` — PreToolUse Tier A regex
- `scripts/public-precommit-runner.sh` — pre-commit Tier A + literal ephemeral
- `scripts/install-public-precommit.sh` — 冪等 stub installer
- `scripts/audit-public-repos.sh` — 定期 sweep
- `.claude/public-repo.marker` — 12 public repo に設置
- `setup.sh` Step 2 + Step 8 更新
- `odakin-prefs/sensitive-terms.txt` (gitignore + network-notes git-crypt symlink) + `work-network.md` placeholder 化
- `odakin-prefs/leak-incidents.md` + `next-steps.md`
- scheduled-task `public-repo-leak-audit-weekly` (毎週月曜 09:23)

**初回 audit 結果**: 12 repo scan、hit 10 sections (全て既存、受容判断済み)、missing markers 0。`leak-incidents.md` に初回 audit エントリ追記済み。

## 過去セッションの変更（2026-04-09 前半）

docs: add sensitive-repo-patterns (ja/en) — 機密情報を含むリポの設計パターン集を `docs/` に追加。conventions: Substack 取得と Gmail MCP read_email の大容量出力パターンを `conventions/substack.md` に記録。

## 過去セッションの完了事項 (詳細は git log + DESIGN.md)

- **2026-04-08**: git-state-nudge.sh に STALE_DIRT 検出追加 (porcelain-hash-age、5 シナリオ検証済)。arxiv-digest cron 根治 (b8f1539)。DESIGN.md に設計判断 90 行追記
- **2026-04-07 夜**: git-state-nudge.sh 拡張 (orphan-tree 検出、noise 削減、update notifier、private リポ名 sanitize)
- **2026-04-07 朝〜昼**: dropbox-refs convention 新規追加 + 3 ラウンド 4 軸チェック
- **2026-04-06**: ARCHITECTURE.md / RUNBOOK 位置づけ決着、CONVENTIONS §2 表の個人層移管、DESIGN/EXPLORING 分離
- **2026-04-03**: PATH 二層防御 (.zprofile + REQUIRED_PATHS snapshot patch)

## 今セッションの変更（2026-04-16）

### README の役割を精査・リライト + 横展開の仕組み化

**契機**: claude-config SESSION.md の残タスク「README の役割精査」。

**分析**: README.md / README.ja.md が CLAUDE.md / CONVENTIONS.md / DESIGN.md と重複 (setup.sh 全手順 1–11 / ディレクトリツリー / conventions/*.md 個別説明 / memory-guard 判別表) しており、ドリフト源になっていた。逆に「訪問者が 30 秒で判断する玄関」としての具体例・非日本語話者向け注記が欠けていた。

**実装**:
- README 2 本を 194→60 行に圧縮。setup.sh 手順・構造ツリー・判別表の転載を削除し CLAUDE.md / CONVENTIONS.md への link に置換。autocompact 復帰の 3 ステップ具体例と "For English-speaking users" 節 (英語版のみ) を追加
- CONVENTIONS.md §2 に `README.md` 行を追加 + 新設「README の流儀」節 (役割・言語別命名ルール・推奨セクション構成 7 項・禁忌 5 項・判定規則・他リポ整備時の適用) を設置。これで他リポが claude-config 準拠になる際に同じパターンで README が整う
- 言語ルール: 英語 README 内に日本語文字を置かない (相互リンクラベルは読み手の言語で)

## 今セッションの変更（2026-04-18）

### claude-config DESIGN.md への §7 retroactive reorg 自己適用

**契機**: LorentzArena 2+1 で 2 回適用した §7 pattern (`docs/convention-design-principles.md §7`) が、規則を定義した claude-config 自身には一度も適用されておらず self-consistency 違反の状態だった。

**実装** (commit `3c55317`): DESIGN.md 4 entries 圧縮 (637 → 576 行、-9.6%):
- symlink 化 (21→8 行) — bundle 判断 LESSON を §1 に昇格
- git history scrubbing 見送り (32→11 行) — DEFER entry 化
- 自己言及的 odakin 記述 (27→12 行) — ACTIVE entry + 削除トリガー
- DESIGN/EXPLORING 分離 (32→3 行) — §6 への pointer 化

convention-design-principles.md 更新: §1 に bundle rule (pragmatic relaxation) 追加、§7.8 に 3 回目適用 段落、§10.8 新設「削除・委譲判断の trap」(6 insights consolidate)。

### session 内の洞察を規約に昇格 (§10.8)

LorentzArena 2+1 の 3 dynamic doc 圧縮 + claude-config 自己適用 session で観察された削除・委譲判断の失敗パターンを §10.8 として durable 化:
- Tier-direction asymmetry (横ずらし委譲は anti-value)
- T0/T1 chain pre-check
- Grep-substitute value (auto-load table = pre-computed grep cache)
- 削除提案の self-correction 事例 (ゲームパラメータ表 anti-value)
- DESIGN.md 分割閾値 (2000 行 / 150 KB / domain 独立 / anchor 曖昧)
- Self-application discipline

詳細は `docs/convention-design-principles.md §10.8` を正本として参照。

### defer 候補 (un-defer トリガー付き)

このセッションで識別した将来の再検討候補:

- **CONVENTIONS.md §2 density audit** — auto-context T0 の一部。un-defer トリガー: 100 行 or 15 KB 到達時に density check。`grep` 頻度が低い section は T1/T2 への移動検討 (§2 表の個人層部分は 2026-04-06 に `odakin-prefs/` へ移管済、今後は claude-config 固有の drift 監視)
- **dropbox-refs.md の narrative 量監視** — 2026-04-07 追加時に 4 軸 review 済だが、類似 narrative style の convention が今後追加されたら系統 pattern としての review 必要。un-defer トリガー: 同じ narrative 癖が他 convention に波及
- **LorentzArena 2+1/CLAUDE.md ゲームパラメータ表の委譲は anti-value (再訪禁止)** — 2026-04-18 に「ROI 高い」と初期判断したが、grep-substitute cost + description column 抽出不能で anti-value と結論。再度委譲を検討しそうになったら §10.8 削除提案の self-correction 事例を先に読む

## 今セッションの変更（2026-04-21）

### 200K コンテキストユーザ向け onboarding 補強

**契機**: 一般ユーザ (200K model、autocompact ≈ 167K) が claude-config を clone した場面で、(1) 規約が unlock されない、(2) context-budget 指針の所在が分からない、(3) CLAUDE.md chain の累積に気付きにくい、という 3 つの onboarding gap を analyze。odakin-prefs は private で一般ユーザ無関係なので、ship する default 側で補う方向に focus。

**実装**:
- `templates/root-CLAUDE.md.default` (17 → 24 行) — 「CONVENTIONS.md を参照」pointer に 4 個の読み込みトリガー (リポ作業開始 / commit+push 前 / 新規リポ作成時 / 記録先判別) を追加。一般ユーザの Claude が規約を実際に読むための cue を provide
- `README.md` / `README.ja.md` — 「Context budget」/「コンテキスト予算」節を Core concepts と Customization の間に新設。200K で combined auto-load を ~50 KB 以下に保つ目安 (§10.7 既存数値を引用) + §10.10–10.11 への pointer
- `docs/usage-tips.md` / `usage-tips.ja.md` — §8「Mind the CLAUDE.md chain in sub-projects」を新設。階層別の役割分離 (top/repo/sub) と 80–100 行 target を記載、§10.10–10.11 pointer

**設計判断**:
- 数値は invent せず `convention-design-principles.md §10.7` の既存閾値 (50KB / 100KB) を流用。閾値は 2026-04-18 odakin 環境 (200K 期 + 1M 期混在) での観測値
- 規約本体 (CONVENTIONS.md) と設計原則 (convention-design-principles.md) は一切変更せず、onboarding doc 側の補強のみ。正本 drift を避ける
- `~/Claude/repo/sub/` を hypothetical example に使用 (`LorentzArena/2+1/` 等の実 repo 名は public-leak 規約上 OK だが、一般向け doc には generic path が適切)
- [ ] **RUNBOOK 系ファイルの実例運用後再検討**: トリガーは「いずれかのリポで CLAUDE.md からランブックを切り出す具体的ニーズが出たとき」。詳細は DESIGN.md「RUNBOOK 系ファイル」セクション参照
- [ ] **規約 rollout 原則の一般化の再検討**: case 2 発生 (RUNBOOK 導入 or 他 content-reorganization 系 convention 追加) で一般原則 (principles §7 新設など) に昇格するか再判断。1 データポイントでの formalize は YAGNI で defer 中
- [ ] **principles.md 昇格候補 4 件の再判定**: 2026-04-08 の STALE_DIRT 関連作業で浮上した 4 原則 (Narrower-but-active、Generator owns commit、Event-driven vs time-driven safety net、Multi-commit workflow checkpoint) の再発時昇格。詳細と un-defer トリガーは `DESIGN.md` 末尾「検討事項: principles.md への昇格候補」参照。**最 strong** は Event-driven vs time-driven (既に対比表あり)、最新で 1 データポイントしかないが緊急性が高いのは Multi-commit workflow checkpoint (人間の指示無しで Claude 自身が横断 sweep を実行する習慣づくり)

### CONVENTIONS.md §2 と §8 の矛盾解消

**契機**: 同日前半の usage-tips Tip 6 書き直し (commit `3a159c2`) は派生 doc を直しただけで、正本 CONVENTIONS.md §2 記録先判別 table が「ユーザーの好み・フィードバック・外部サービスへの参照 → メモリ」のままだった（§8.3 の `memory-guard.sh` deny と逆向き）。spawn task prompt を usage-tips に scope 限定していたため agent が upstream まで遡れなかった。

**実装**:
- §2 記録先判別 table の 1 行を 3 行に split: machine-local 事実・外部サービス参照 → memory（§8.5・§8.7）/ 恒久的好み・身元情報 → 個人層 or `CLAUDE.md` chain（§8.6）/ 再発防止 feedback → `conventions/*.md` or hook or 書かない（§8.2・§8.3・§9.1）
- §2「よくある間違い」に feedback → memory 違反を追記
- §3 SESSION.md 運用行 + 4 軸 efficiency check の 2 箇所: "MEMORY.md 150 行以内" → "index-only（§8.7）"

**LESSON**: self-contradiction を修正する際、spawn task prompt の scope を symptom (usage-tips) に限定すると agent は upstream source (CONVENTIONS.md) を認識できない。`grep -rn <矛盾キーワード>` で repo 全体を確認してから prompt を起草する。

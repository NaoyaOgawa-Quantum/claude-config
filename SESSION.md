# SESSION — claude-config

## 現在の状態

**2026-05-06 (afternoon)**: `conventions/android-chromium-remote-debug.md` 新設 (commit `1c7b271`)。 同日 LorentzArena Bug 14 live state capture (= スマホで 15.77h 動いていたタブから reload 前に state 完全 dump) で確立した、 Android Brave/Chrome の remote debugging procedure を universal applicable な convention に外出し。 7 節構成 (= 経路選択 / WiFi ADB / CDP / Runtime.evaluate origin workaround / mobile-only bug RCA pattern / 注意点 / References)。 §5 RCA pattern の中核は (a) `performance.now()` vs `Date.now()` で background suspend 時間を逆算、 (b) live state capture before reload、 (c) ring buffer GC を意識した「真因 event 痕跡が消える」 problem 対応。 odakin-prefs/work-discipline §+2 (= USB ADB が詰まったら WiFi ADB first-line / mobile-only bug は reload 前に live state 吸い出す) で odakin 適用 procedure 並設、 LorentzArena meta-principles §M41 (= β/γ diagnostic) + §M42 (= ring buffer GC) + §M35 update (= LH ratchet 仮説の最終否定 with live data confirm) で project-specific 知見化。 3 層 (universal / odakin / project) 配置。

**2026-05-06**: `docs/convention-design-principles.md §11` 新設「In-plan exploration trail — single-session walkback の保存」 (commit `fb8065c`)。 LorentzArena 5/6 NPC 非対称 causality plan で (I) → (II) → (II'') → (II''') の 4 案を経て (II)/(II'') の 2 段 walkback で着地した経験から抽出。 §6 EXPLORING.md (= cross-session 探索) と独立な軸として、 same-session 内 plan iteration の trail を plan §1.6 「探索過程」 で時系列保存する pattern。 §11 「やらないこと」 (decision-form) と §1.6 (process-form) は重複せず補完。 §11.1-11.6 で問題定義 / §6 との違い / 解決 pattern (template) / 適用判断 / §11 との関係 / 適用事例。 odakin-prefs/work-discipline.md 側にも 4 件の odakin 適用 procedure (= plan §1 framing で false premise を作らない / common principle ad-hoc 統合禁止 / §1.6 trail 保存手順 / 構造的 constraint 確認先行) を併設、 LorentzArena meta-principles §M35-M40 に project-specific 知見 (= NPC 非対称 / mean vs midpoint / type-level discriminator / (α) 永続却下 / dead asymmetric / friction bound) を 6 件永続化。 3 層 (claude-config universal / odakin-prefs procedure / LorentzArena project) で重複なく補完する配置。

**2026-05-02**: `conventions/shared-repo.md` に §「macOS LaunchAgent / launchd plist の literal-path trap」 を新設 + §「公開前の Audit」 にカバレッジ ギャップ注記を追加。某 private shared 共著論文リポに PDF auto-publish (mobile reading 用 LaunchAgent) を入れた直後、plist の `ProgramArguments` / `WatchPaths` が `~`/`$HOME` を展開しない macOS の特性で `/Users/<owner>/...` literal が焼き付き layer-2 違反 (= shared-repo §「公開前の Audit」 の grep が 0 件で無くなる) を crit。template (`__HOME__` placeholder) + `setup.sh` (sed 置換 + launchctl bootstrap、冪等) の解法を recipe 化。同種 trap (LaunchDaemon plist / Hammerspoon Lua)、systemd `%h` / Windows env var の native 展開対比も併記。あわせて「`public-leak-guard.sh` chain は public marker 付きリポしか fire しない、private shared リポの layer-2 audit は session-end の手動 grep に依存」 をカバレッジ ギャップとして注記 (今回の事故の発見経路は手動 audit で commit 1 つ後の検出 → 即 fix の小コストで済んだが、構造的には次回も同じ経路で発見される)。

**2026-05-01**: 個別リポでの「git fetch first」 + 「MCP 中断時の復旧」の規約整備 (4 commit):
- `cde652e` (CONVENTIONS §3): リポ作業開始手順に `git fetch` を一級項目として追加。`git status` の "up to date" は fetch 前なら stale ref に基づく嘘である理由を明記。同日 twcu-phys-lab で fetch 省略 → non-fast-forward reject 事件が起点。
- `b8b9a46` (個別連動 push-workflow.md): 同日朝の twcu-phys-lab 事件を起点に「任意 → 必須」格上げ。各 personal-layer の push-workflow.md と相互参照。
- `105718a` (conventions/mcp.md): 「MCP 接続失敗時のセッション内復旧 runbook」節を新設。Claude Code の stdio MCP は session 起動時 bind で in-session reconnect 経路がない (上流 bug #20684 / #33468) 制約下での 6 段復旧手順 (状態確認 → 素手 stdio handshake → log 確認 → remove+add 再登録 → /mcp UI → claude --resume → 根本原因 checklist) + Chrome MCP の別経路扱い + 同日 classroom-cis incident 事例。
- 5 月新スクリプト (odakin-prefs/scripts/upcoming-irregular-events.py + shift-worship-period.py) との連動: events.yaml の irregular event を 2 週前から surface する dashboard 補強と、礼拝期間時限繰下げを CIS calendar に冪等反映する自動 sync。本リポ規約面では特に追加なし、odakin-prefs/DESIGN.md §2026-05-01 に詳細記録。

**2026-04-29 (続)**: `conventions/japanese-email-honorifics.md` を新規作成。「身内に対して『様』『皆様』を使わない」という universal な日本語敬語ルールを公開規約として成文化。由来は同日のある研究セミナー業務セッションで、外部宛メール draft で身内側 (同僚と自分・研究室メンバー) に「皆様」を付けてしまい user から「身内に皆様は敬語おかしいやろ」と訂正されたケース。内 vs 外の区別、「様」「皆様」を身内に使わない原則、「先生」「さん」も同様、同姓内外の切り分け方を含む。

**2026-04-29**: `conventions/research-email.md` に §「研究者連絡先 (email) の取得手順」を追加 (commit `2627468`)。論文 PDF 1 ページ目を最優先、所属機関の公式メンバーページ・OpenReview・Semantic Scholar は mask されることが多いため後回し、という lookup priority を明文化。失敗例 (twcu-seminar 2026-04-28 セッションで小島武さん依頼時に発生 — メンバーページ mask を見て user に尋ねたが arXiv PDF を見ればすぐ取れた case) と、取得経路を `researchers.yaml` notes に記録する規律も追加。

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

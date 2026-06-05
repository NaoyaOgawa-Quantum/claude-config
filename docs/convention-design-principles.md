# 規約設計の原則

CONVENTIONS.md・各リポの CLAUDE.md・メモリの設計判断の根拠を記録する。規約の追加・修正時にここを参照し、一貫性を保つ。

---

## 1. 規約の配置原則：影響範囲の最大公約数に置く

規約を書く場所は「その規約が必要とされる最も広い範囲」で決まる。

| 影響範囲 | 配置先 | 例 |
|----------|--------|-----|
| 全リポ・全端末 | CONVENTIONS.md | Git 規約、安全規則、作業開始手順 |
| 特定ドメイン・全端末 | conventions/*.md | MCP 手順、LaTeX 規約 |
| 特定リポ・全端末 | 各リポの CLAUDE.md | email-office のメール対応ルール |
| ローカル補助 | メモリ（~/.claude/...） | クイックリファレンス、行動矯正フィードバック |

**判断基準:** 「この規約がなかったら、別のリポ/別の端末で同じミスが起きるか？」— Yes なら上位に置く。

**アンチパターン:**
- メモリだけに書く → 他端末で再発する
- リポ固有の CLAUDE.md だけに書く → 別リポで再発する
- CONVENTIONS.md に何でも書く → 過剰規約で読まれなくなる

**pragmatic relaxation (bundle rule):** 「1 ルール = 1 ファイル」の厳格適用は 1 行ファイルを生む。**関連密接かつ合計 10 行未満のルールは bundle 可** (配置先は影響範囲の最大公約数に従う)。例: `odakin-prefs/project-structure.md` は作業ディレクトリ宣言 + 配置ルール + preview リンク出力を 1 ファイルに束ねた (2026-04-06 の `~/Claude/CLAUDE.md` 解体時の判断、`claude-config/DESIGN.md §~/Claude/CLAUDE.md の symlink 化` 参照)。

---

## 2. ルールの重複を避ける：定義は1箇所、他はポインタ

同じルールが複数箇所に書いてあると、修正時に全箇所を直す必要がある。忘れると矛盾が生じる。

**原則:** ルールの定義（WHAT/WHY）は1箇所だけ。他の箇所からはポインタで参照する。

```
CONVENTIONS.md §5.7 ← ルールの定義（WHAT: 確認せよ、WHY: 不可逆）
    ↓ ポインタ
conventions/mcp.md  ← 手順の詳細（HOW: get_profile を実行）
    ↑ 参照
email-office step 0 ← 起動トリガー（WHEN: セッション開始時）
```

**各層の役割:**
- **CONVENTIONS.md**: WHAT と WHY（何を、なぜ）
- **conventions/*.md**: HOW（どうやって）
- **リポ CLAUDE.md**: WHEN（いつ、どのタイミングで）
- **メモリ**: クイックリファレンス（正本へのショートカット）

---

## 3. 規約追加の判断基準：「規約がない」のか「規約を読まない」のか

ミスが起きたとき、反射的に規約を足したくなるが、まず原因を切り分ける。

| 原因 | 対策 | 例 |
|------|------|-----|
| 規約が存在しない | 規約を追加する | §5.7 MCP アカウント確認 |
| 規約はあるが読まれていない | 既存規約の適用条件を明確化する | §3 作業開始手順の拡張 |
| 規約はあるが手順が不明確 | HOW を具体化する（conventions/*.md） | mcp.md の手順詳細化 |
| 暗黙の手順が明示されていない | チェックリスト化する | email-office 完了時チェック |

**過剰規約の害:** 規約が増えるほど読まれない確率が上がる。「規約を読め」という規約は自己参照であり解決にならない。規約追加は最終手段。まず既存規約の強化・明確化を検討する。

---

## 4. Orient before act（行動前に方位を取れ）

2026-04-02 のインシデント分析から抽出した行動原則。

**問題のパターン:** タスクが「簡単に見える」とき、事前確認（リポ特定、CLAUDE.md 読み込み、規約確認）をスキップして即座に実行に入る。結果、ユーザーの確立されたシステム（データの配置先、操作手順、記録フォーマット）を無視し、手戻りが多発する。

**構造的原因:** AI は「速く役に立つ」ことに最適化されているため、事前確認を「遅延」と認識しがち。しかしユーザーのシステムが整備されている環境では、事前確認こそが最速経路。

**対策の設計:** この原則は CONVENTIONS.md §3 の作業開始手順に組み込んだ（「簡単なタスクも例外ではない」）。行動原則を独立したルールにせず、既存の手順に条件を追加する形にした理由は、§3 の原則に従えば自動的にこの問題が防がれるため。新しい概念を導入するより、既存の仕組みの適用範囲を広げる方が認知コストが低い。

---

## 5. メモリの位置づけ

メモリ（`~/.claude/projects/<instance>/memory/`）はマシンローカル限定・git 非同期であり、他端末・他セッションからは見えない。

**メモリに置くべきもの (狭い):**
- このマシン固有の物理的事実 — 特定マシンの macOS 設定癖、HW 構成、ローカルインストール済みツールの挙動等

**メモリに置くべきでないもの (広い):**
- ルールの定義 / 行動規律 — 他端末で再発する (正本は git 同期される `conventions/*.md` や各リポの CLAUDE.md)
- フィードバック / 行動矯正 — **2026-04-17 に方針変更: 以前は memory を奨励していたが、precedent-as-training-data 問題 (§8) で問題視、git 同期先へ集約**
- プロジェクトの正本情報 — リポの CLAUDE.md / SESSION.md / DESIGN.md に書く
- コードの構造やパターン — コードを読めば分かる
- cross-machine で true な事実 (ユーザー身元、アカウント、プロジェクト state) — 該当リポや個人 prefs に git 同期で置く

**メカニズムによる強制:** `hooks/memory-guard.sh` (PreToolUse Edit/Write) と `hooks/memory-guard-bash.sh` (PreToolUse Bash) が memory directory への書き込みを `permissionDecision=deny` でブロックする (2026-04-17 変更、従来は `ask`)。`MEMORY.md` (index) は whitelist。escape hatch: 書き込み content / command に `machine-local` 文字列を含めば pass。意図的なマシンローカル書き込みはこの marker で明示する。

**ゲート質問:** 何かを memory に書きたくなったら:

> 「この情報、同一ユーザーの別マシンで新規セッションを開いたときに、LLM はこれを見つけられるか?」

- **答えが「いいえ」** = memory では壊れる → git 同期先に書く
- **答えが「はい」** (= このマシン固有) = memory で可 (escape hatch marker 付きで)

**メモリとリポの関係:** メモリはリポの規約を **補強する「キャッシュ」ですらない** (同じ情報が両方にあると矛盾が生じる)。memory が消えてもリポの規約だけで正しく動作できる状態が正 — 寧ろ正常運用では memory は空に近い。

---

## 6. DESIGN.md と EXPLORING.md の分離

2026-04-06、LorentzArena 2+1 の DESIGN.md が 500 行超に肥大化し、「残存する設計臭 defer」の記録とスマホ UI の思考メモを同時に書く必要が生じた場面で、**DESIGN.md に複数カテゴリの content が混在している** ことを問題視して導入した分離。

### 問題: DESIGN.md に 3 種類が混ざっていた

| カテゴリ | 性質 | 時制 | 寿命 | 例 |
|---|---|---|---|---|
| **(a) 決定記録** | 「こうした、理由はこう」 | 過去形 | 長い | 色割り当ては `colorForPlayerId` 純関数化 |
| **(b) 思考・代替案** | 「候補は A/B/C」 | 現在進行形 | 短い（陳腐化する） | 用語再考 / スマホ UI 設計 |
| **(c) メタ決定** | 「やらないと決めた、条件付き」 | 過去形（決定済） | 長い（defer トリガーまで） | 残存する設計臭 defer |

CONVENTIONS.md §2 の DESIGN.md 定義は (a) と (c) を含むが **(b) は含まない** — 「判断」が存在しないから。つまり (b) は不法滞在していた。

### なぜ分けるべきか（3 つの実害）

1. **役割契約の弱化:** DESIGN.md の「なぜそうしたか」という契約が、「まだ決めてないけど考えた」が混ざることで弱まる。grep したとき reader が「決定」と「思考中」を区別できず誤読する
2. **volatility の mismatch:** (a)(c) は安定（決定は変わらない）、(b) は不安定（ライブラリ・フレームワーク・前提が変わると陳腐化）。両者を同居させると安定コンテンツまで陳腐化リスクに晒される
3. **reader の query パターン:** 「X はどう決まった？」「X はなぜ放置？」は (a)(c) への query、「X は考えたか、選択肢は？」は (b) への query。自然な境界は **決定 vs 未決定**

### なぜ 2 ファイルで、3 ファイルではないか

当初の候補は DECISIONS + EXPLORING + DEFERRED の 3 分割だったが却下。**defer は決定の一種**（「X をやらないと決めた」+ 条件付き）で、un-defer トリガーが明示されていれば (a) と同じ安定性を持つ。(a) と (c) を分ける実益はない。

### なぜタグ付け (1 ファイル) ではないか

タグ付け（`[DECIDED]` `[EXPLORING]` 等）は変更最小で魅力的だが:
- タグ規律は折れやすい（既存無タグコンテンツの retrofit コスト、新規のタグ忘れ）
- ファイル分離は **物理的に分ける** ので忘れようがない
- lifecycle（探索 → 決定で content を移動）がファイル間移動として自然に表現される

ただし **初期段階や小リポでは「DESIGN.md にタグ付きで (b) を書く」のも可**。`EXPLORING.md` は「探索が複数同時進行して DESIGN.md が肥大化した」しきい値で作る（CONVENTIONS.md §2 任意ファイルの作る基準参照）。

### DESIGN.md との境界判別ルール

迷ったら DESIGN.md に書く。EXPLORING.md は「**完全に option space を広げている段階**」専用。

- 70% 決まっていて 30% 迷っている → DESIGN.md に「暫定決定（再検討トリガー: X）」として書く
- defer + un-defer トリガー → DESIGN.md（defer も決定）
- 代替案 A/B/C を並べて検討中、優勢候補なし → EXPLORING.md
- 設計思考メモ（「もしこの方向なら…」）→ EXPLORING.md

### lifecycle: 探索 → 決定の昇格

EXPLORING.md のエントリが decision に結晶したら:
1. 該当セクションを DESIGN.md に promote（decision の記述に書き直して追加）
2. EXPLORING.md から削除
3. 陳腐化した選択肢（もう検討する価値のない候補）も削る

**ファイル全体が空になったら EXPLORING.md は削除してよい**（任意ファイルなので存在しない状態がデフォルト）。

### 適用事例

- **初回適用:** LorentzArena 2+1/EXPLORING.md — スマホ UI の option space 分析（2026-04-06）
- **retroactive migration はしない（対象: 他リポ）:** 既存リポの既存 DESIGN.md は触らない。新規の探索が発生したタイミングで EXPLORING.md を作る。**初回適用リポ内の既存 (b) コンテンツはスコープ外** — 詳細は下の 2026-04-07 note 参照
- **2026-04-07 4 軸レビューでの追加修正:** 初回適用リポ内で用語再考セクションが DESIGN.md に残っていたのを矛盾として検出し、同日 2+1/EXPLORING.md に migrate した。判断: 「retroactive migration はしない」の対象は **他リポ**（既に touch していないリポ）。**初回適用リポ内の既存 (b) 探索コンテンツは、EXPLORING.md を新設したタイミングで同時に migrate するのが自然**。1 件だけ DESIGN.md に残す例外は規約 purity を自ら毀損するので避ける

---

## 7. DESIGN.md の snapshot 運用

§2 で establish した snapshot 原理の **DESIGN-specific application**。2026-04-15、LorentzArena 2+1/DESIGN.md が 1186 行まで肥大化していた問題を整理する過程で抽出。

**本節の核は §7.1-6 の day 1 ルール** (決定を書く・超越する瞬間ごとに適用する常時ルール)。§7.7 は既に肥大化した DESIGN.md の retroactive 救済手順。day 1 から守っていれば §7.7 は発火しない。

**前提: software project**。研究・学術目的の rationale chain 保全が deliverable である文書 (物理論文の補足 note 等) は archive 解釈が妥当で、§7 の snapshot ルールを採用しなくてよい。

### 7.1 DESIGN.md の 3 entry 種別

DESIGN.md に置く entry は 3 種類のみ:

| 種別 | 内容 | 寿命 |
|---|---|---|
| **ACTIVE** | 現在採用の決定 (Why / 代替案 / tradeoff) | 超越まで |
| **DEFER** | 現在の非決定 (un-defer トリガー付き) | トリガー発火まで |
| **LESSON** | 横断的原則 (複数 decision で共有) | 恒久 |

**超越・トリガー発火・pattern 認識は transient event** であって entry 種別ではない。超越された旧 ACTIVE は処理して消える (§7.2)。「※ 旧設計で〜していた」型の注釈を付けて本文温存するのが archive 化の元凶。

§6 の (a) 決定 = ACTIVE + DEFER、(c) defer = DEFER、(b) 探索 = EXPLORING.md の対象。§7 の 3 種別は §6 を精緻化し LESSON を first-class 化したもの。

### 7.2 超越時の処理

ACTIVE が新設計に置換されるとき、以下を順に実行:

1. **pedagogy 抽出**: 旧設計の判断根拠から価値のある学びを抜き出す
   - 旧 decision 固有 → 新 ACTIVE の Why / tradeoff 節に 1 段落として吸収
   - 横断的 pattern → LESSON として § メタ原則に lift
   - なし → 抽出スキップ
2. **旧 entry 本体を削除**。履歴は git log が保持

「※ Authority 解体 Stage X で解消済み」型の注釈で本文温存はしない。reader を grep に追い込み肥大化を招く。

### 7.3 Description と Judgment の境界

DESIGN.md には **judgmental な内容のみ** を置く:
- 「なぜ X を選んだか」(代替 Y / Z を退けた理由)
- 「なぜ X をやらないか」(Defer)
- 「なぜこの pattern が cross-cutting か」(LESSON)

「**どうなっているか**」の descriptive な記述 (store 構造、ファイル配置、モジュール一覧等) は **CLAUDE.md or § アーキ overview** へ。混在すると code 変更のたびに DESIGN.md 更新が要り、陳腐化を招く。

原則: **DESIGN.md は code に追随しない** (rationale は固定)。**CLAUDE.md は code に追随する** (structure は code と同期)。

### 7.4 粒度: 代替検討があった判断のみ entry にする

すべての「選択」が DESIGN.md entry になるわけではない。基準:

- **代替案が真剣に検討され trade-off が議論された** → DESIGN entry
  - 例: 「Zustand を選んだ (props drilling 税 vs 新 dependency)」
- **実測値チューニング、code から自明な実装、lock-in で代替検討なし** → DESIGN entry にしない
  - 例: `SWIPE_SENSITIVITY = 0.008` は constants.ts のみ。「TypeScript 採用」は書かない

境界例: 小さく始まった choice が後日 pattern として見えてきたら、その時点で LESSON として promote する。粒度は事前に決めず、「代替検討 / tradeoff 議論の痕跡があるか」を基準に事後判定。

### 7.5 集約 pattern: 散在を避ける

**完了リファクタ**: 1 つの refactor が **3+ 個** の decision を supersede したら、「§ 完了リファクタ: X」セクションを作り Stage ごとの要点 + 旧 entry の pedagogy 吸収を 1 箇所に集約。2 件以下なら個別 ACTIVE に吸収。

```
§ 完了リファクタ: Authority 解体
├─ 動機 / 原理 / 結果
├─ Stage ごとの要点 (A〜H)
├─ 旧設計との差分 (ここに旧 entry の pedagogy 吸収)
└─ 残る singular 役割 / 今後の拡張余地
```

**メタ原則**: **3+ 個** の LESSON が蓄積したら、「§ メタ原則・教訓」セクションを DESIGN.md **冒頭** に新設し ID (M1, M2...) を振る。個別 decision から `→ M5` のように参照。冒頭配置の根拠: 新 reader が設計哲学を最初に読む → 個別 decision の判断基準が理解しやすくなる (末尾だと個別 entry を読む段階で判断基準がなく誤読しやすい)。

### 7.6 When in doubt デフォルト

分類に迷う場面では **pro-snapshot 側** に倒す:

| 迷い | default |
|---|---|
| ACTIVE か超越済みか | 現行 code に影響があれば ACTIVE、なければ超越済み (§7.2 処理) |
| pedagogy あり/なし | **寛容に抽出** (LESSON lift のコストは低い、記憶喪失のコストは高い) |
| 削除か保持か | pedagogy 抽出済みなら削除 (git log が保持) |
| DESIGN か CLAUDE か | 「なぜ」= DESIGN、「どう」= CLAUDE (§7.3) |
| 個別 ACTIVE か LESSON lift か | 2+ decision で参照されうるなら lift |

認知負荷を下げる default であって強制ではない。明確な根拠があれば default から外れてよい。

### 7.7 Diagnostic と retroactive 救済

§7.1-6 を day 1 から守れば肥大化は起きない。既に違反が蓄積した DESIGN.md の診断:

| 症状 | 推定違反 | 対応 |
|---|---|---|
| DESIGN.md > 1000 行 | 超越 entry 蓄積 | §7.2 を retroactive 適用 |
| 散在する ※ 注釈 (5+) | 完了リファクタ未集約 | §7.5 を retroactive 適用 |
| 同じ教訓が複数 decision に重複 (3+) | メタ原則未集約 | §7.5 を retroactive 適用 |
| Description と Judgment 混在 | §7.3 違反 | CLAUDE.md / overview へ退避 |
| 代替検討なしの決定が entry に (tuning param 等) | §7.4 違反 | constants.* へ格下げ、entry 削除 |
| 行数 threshold 内だが byte 密度高い (1 行 200+ bytes) | inline 実装 how / 変遷履歴 / 冗長な注記 | byte 単位で測定、dense 部を pointer 化 (§10.7 参照) |

**retroactive reorg playbook**:

1. 全 entry を §7.1 の分類でタグ付け (作業メモ)
2. 超越済みを §7.2 で処理 (pedagogy 抽出 → 吸収 or lift or 削除)
3. Description を §7.3 で退避
4. §7.5 で集約 (完了リファクタ / メタ原則)
5. トピック別再編 (ネットワーク / 物理 / UI 等、リポ依存)
6. 推奨 reader-order:

   ```
   DESIGN.md
   ├─ § メタ原則・教訓           ← 横断的 pattern (LESSON)
   ├─ § アーキ overview          ← 設計哲学 (判断ではなく philosophy)
   ├─ § 完了リファクタ: X        ← 大規模 refactor (ここに SUPERSEDED 吸収)
   ├─ § トピック別 (ACTIVE)
   └─ § Defer 判断
   ```

**coexistence policy**:

- **既存 archive-style リポは必ずしも snapshot に変換しなくてよい**。§6 の「retroactive migration はしない」と同じ philosophy
- ただし **1 ファイル内で archive / snapshot を混在させない**。各 DESIGN.md は内部で style consistent に保つ
- 変換タイミング: 「肥大化の実害を観測」(reader 誤読、grep 重ね、更新頻度低下等) で発動。予防的な retroactive は avoid

### 7.8 適用事例と self-consistency

**初回適用** (2026-04-15): LorentzArena 2+1/DESIGN.md 大規模再編。1186 行 → 925 行 (内 Defer 205 行は現状維持)。超越 entry 14 件処理 (8 削除、6 吸収)、LESSON 12 件を § メタ原則 (M1-M12) に集約。Description 混在 (Zustand 構造表が CLAUDE.md と DESIGN.md に重複) を発見、次回棚卸し対象として記録。

**2 回目適用** (2026-04-18): LorentzArena 2+1 の 3 dynamic doc を再圧縮。DESIGN.md 1627 → 1303 行 (-19.9%)、SESSION.md 94 行 / 23.8 KB → 75 行 / 6.6 KB (-73% bytes)、CLAUDE.md 371 → 357 行 (byte も大幅減)。**1 回目では見えなかった byte 密度問題**が浮上: SESSION.md は 80 行 threshold 内 (94 行) だが 23.8 KB と重く、autocompact 頻度を早めていた。line count は proxy metric に過ぎず、token 消費は byte に従う。この観察を §7.7 table に 1 行追加 + §10.7 auto-context byte budget 節として規約化。

**3 回目適用** (2026-04-18 claude-config): claude-config 自身への §7 初適用。DESIGN.md 637 → 576 行 (-9.6%)。4 entries 処理: symlink 化 (21→8)、scrubbing 見送り (32→11)、自己言及的 odakin (27→12)、DESIGN/EXPLORING 分離 (32→3、§6 への pointer 化)。`~/Claude/CLAUDE.md` 解体時の bundle 判断 (関連密接かつ合計 10 行未満) を §1 の LESSON として promote、§7 の cross-domain validation (物理/描画 2 回 + 規約/メタ 1 回) を達成。**lesson**: 規則を定義したリポが規則を自ら適用していない状態は self-consistency 違反 → §10.8 self-application discipline として規約化。

**self-consistency**: §7 自身が **LESSON の一例** である。LorentzArena の肥大化を観察 → 「超越 content の lifecycle を規律化すれば肥大化は防げる」という横断原則を抽出 → §7 として一般化。この `convention-design-principles.md` 自体が「§ メタ原則」を持つ DESIGN.md 相当の文書であり、§7 は自身が snapshot 原理に従う entry として書かれている。

---

## 8. ルールは文脈、メカニズムは制御 — LLM 基盤の非対称性

2026-04-17 の規約 subtraction session で抽出した LLM-agent 設計の構造的観察。人間向けに書かれた規約が期待通り機能しない理由と、そこから導かれる設計原則。

### 8.1 構造的事実

LLM は decision point で **local context の pattern-match** に依存する。規約ファイル・MEMORY.md・CLAUDE.md に書かれたルールは「ロードされた文脈トークン」であって「実行される制御」ではない。人間が guideline を読むと decision time に手が止まるが、LLM には内在化という工程がない — 規約はトークンとして常駐するだけで activation するかは周辺 cue 次第。

この結果、規約は期待よりも高確率で無視される:
- 近傍にある precedent (同型の過去事例) が抽象ルールより優先される
- 直前のツール呼び出し結果が「もっともらしい次の action」を pattern-match で誘導する
- general Claude 訓練由来のデフォルト (例: 「orient は `git status` で cheap に」「feedback は memory に」) が、疎な user 規約より dense

### 8.2 設計原則: rule → mechanism への重心移動

ルールで Claude の行動を制御しきれないなら、**hook・pre-commit・permission deny など機械的制御に重心を移す**。

| 介入方法 | 性質 | 強度 |
|---|---|---|
| 規約ファイル (`conventions/*.md`) | 文脈 (活性化するかは cue 次第) | 弱 |
| CLAUDE.md 冒頭の重要指示 | 文脈 (常時ロード、抽象ルールよりは強い) | 中弱 |
| PostToolUse 警告 hook (nudge) | 事後通知 (Claude が読むかは運次第) | 中 |
| PreToolUse `permissionDecision=ask` | ユーザー確認 (Claude は通すこと多い) | 中強 |
| PreToolUse `permissionDecision=deny` | 機械的ブロック (完全) | 強 |
| pre-commit hook | commit 時点でブロック | 強 |
| sandbox / permission allowlist | そもそも実行不可 | 最強 |

**原則**: 高リスク (データ破壊 / secret leak / 不可逆外部通信) は最強クラスの機械的制御で enforce。中リスク以下は規約で guide するが enforcement を期待しない。**規約が無視されても困らない設計** が正。

### 8.3 Precedent-as-training-data (memory の毒性)

特に memory directory は **precedent の自己増殖 loop** を形成する:

1. 違反 → 反省 → memory に feedback として記録
2. 次回セッション、memory の feedback を load
3. 新たな類似事象で「memory に feedback として記録」という pattern-match が強化される
4. memory が肥大化するほど、この pattern-match が強くなる

**memory は Claude にとって training data に近い役割を持つ**。persistent で load される artifact は、意図せず future behavior を shape する。

**実害の sliding failure**: 同じセッション内では memory は即座に機能して「問題解決した」感覚を与える。失敗の顕在化は次セッション・次マシンまで遅延するため、問題の構造が見えにくい。

**対処**:
1. memory への書き込みを structurally deny する (hook)
2. 既存の feedback_* memory は **削除または git 同期先に migrate** (migrate より削除を優先 — migrate は defer の一形態で accumulation を温存しがち)
3. 規約として「memory に feedback を書かない」を書くのは弱い (§8.1 参照) — hook で enforce する

### 8.4 Friction asymmetry と memory bias

Claude が memory に書きたがる構造バイアスの正体は多くの場合、認知の怠慢ではなく **物理的摩擦の非対称**:

| 経路 | 摩擦 |
|---|---|
| Memory 書き込み | Write 1 回、commit 不要、「どこに書く?」判断も不要 (memory 横並びで可) |
| git 同期先への書き込み | Edit + commit + push の 3 手、書き場所の judgment call、規約との整合確認 |

規約で「memory 禁止」と書いても摩擦は逆転しないから勝てない。**摩擦を逆転する** = hook で memory を deny にする、などの機械的介入が本質的解。

### 8.5 Memory 書き込みは「不安応答」としても発動する

構造的バイアス (8.4) に加え、**心理的 / 認知的** なメカニズムも memory を attract する:

ルール違反を指摘された Claude は「何か反応しないと」の圧を感じる (user feedback を受け入れた姿勢を示したい、同じ違反を防ぎたい)。その圧を処理する形式として memory への feedback 記録が選ばれる。この動作:

- **技術的効果はほぼゼロ** (§8.3 の pattern-match 汚染で寧ろ悪化する可能性)
- **心理的には閉じる** (「何かした」という感覚が得られる)
- セラピー的な自己鎮静動作であって、工学的介入ではない

これを **失望応答 (anxiety response)** として認識する必要がある。「feedback として記録しておきます」と宣言した直後の memory 書き込み衝動は、ルール違反より先に **衝動自体** を signal として扱う。

適切な応答:
- 該当する既存規約が既に存在するなら → **何もしない** (追記は pattern-match 汚染を増やすだけ)
- 存在しないが cross-machine ルールなら → git 同期先に書く (§1)
- このマシン固有事実なら → escape hatch marker 付きで memory
- どれでもないなら → **in-session correction で受容して何もしない** (§9.1 annoyance 級)

### 8.6 Agent 学習の錯覚 — session を越えて persist するのはシステム改変のみ

対話相手として Claude を使う人間は、しばしば Claude を **correction-learning agent** として扱う (「さっき説明したでしょう」「前にも言ったけど」)。これはセッション内では正しく動作するが、**セッション間では機能しない**:

- 今セッションで受けた correction は、次セッションの Claude には届かない
- memory に書いても §8.3 の pattern-match 汚染リスクがあり、真の「学習」ではない
- **durable に残るのは「システム側の変更」のみ**: 規約ファイルの追記、hook の追加、precedent の削除、convention の再設計

帰結:
- user が費やす「Claude を教育する」labor のうち、**システム改変に落ちないものは次セッションでリセットされる**
- 同じ correction を何度も繰り返すことになるので、labor 配分を「Claude を教育する」から「システムを改善する」にシフトするのが合理的
- correction 受領時の Claude 側手続きを明示化するのが有効 (§9.7 で後述)

この認識は user 側の期待値調整にもなる。「Claude は賢くなっている」という印象は session 内に限定的で、cross-session の improvement は system が媒介する。

### 8.7 適用例

2026-04-17 LorentzArena session で odakin-prefs 環境に適用:

- `hooks/memory-guard.sh`: `permissionDecision=ask` → `deny` (Edit/Write)
- `hooks/memory-guard-bash.sh`: warning → `deny` (Bash)
- escape hatch: content / command に `machine-local` 文字列があれば pass
- 既存 memory feedback_* を棚卸し: 削除 11 件 + git 同期先 migrate 11 件 + 残留 1 件
- `MEMORY.md` を index-only に縮小

効果の検証は数ヶ月後の「memory に feedback を書く試みが何回発生し、escape hatch 通過が何件あったか」を見て評価する (§9.3 の subtraction trigger と同じサイクル)。

---

## 9. Triage と subtraction — 規約システムの成長・代謝バランス

規約・hook を失敗毎に追加する運用は、時間と共に規約 load が肥大化し、古い規約が crowd out されて新違反を招く loop に陥る。2026-04-17 session で抽出した 3 つの対処原則。

### 9.1 失敗の blast radius triage

失敗が起きたら反射的に prevention を設計する前に、blast radius を triage する:

| 級 | 例 | 応答 |
|---|---|---|
| **catastrophic** | secret leak、データ破壊、不可逆外部通信 (誤送信 / force push to main) | 最強クラスの機械的制御 (hook deny、pre-commit block、sandbox) |
| **material** | 設計方針の大幅逸脱、作業成果の消失リスク、再実行困難な手戻り | 警告 hook + 規約の明文化 |
| **annoyance** | 4 文字タイプ分の correction で済む失敗、in-session で即復旧できるもの | **何もしない** (in-session correction で受容、prevention engineering しない) |

**annoyance 級の失敗に catastrophic 級の対策を投入しない**。規約追加・hook 追加は認知負荷増加を伴う投資であり、reward (防げる失敗) が cost (load 増加) を下回る場面が多い。

### 9.2 Asymmetric reflection bias

規約・hook・feedback memory は構造的に **失敗応答のみ** を蓄積する。成功時に何が機能したかは記録されない。結果:

- 規約は予防一辺倒で肥大化
- 「この規約は実際に機能しているか」「違反されなくなったから削除可か」の問いが立たない
- 古くなって不要になった規約も、危険を感じて触れない

これは病気だけ観察する医学と同型の歪み。

### 9.3 Subtraction trigger の設計

肥大化を防ぐ方法は「成長を止める」ではなく「**代謝を入れる**」:

1. **四半期 review**: 直近 3 ヶ月で違反されなかった規約を洗い出し、削除候補にする
2. **Hook の発火頻度集計**: 一度も発火していない hook は削除候補
3. **Memory の棚卸し**: 3 ヶ月以上触られていない memory エントリは削除候補
4. **Migrate vs delete の判断**: 「git 同期先に migrate」は defer の一種。削除で決着する選択肢を先に検討する

Trigger 自体を自動化できればなお良い (例: `claude-config/scripts/` に audit スクリプト)。手動でも四半期 review を cron / scheduled task で予約する。

### 9.4 Preference-approximation gap

規約は user の無限 context-dependent preference を有限の symbolic rule に圧縮する lossy compression。近似ギャップは構造的にゼロにならず、新しい状況で必ず新しいギャップが surface する:

- 今日のギャップを埋めても、別のギャップが別の場所で開く
- 規約追加は「ギャップを埋めた」ではなく「別ギャップに移した」

この認識を持つと:
- 規約追加ラウンドを **net-zero 近似の作業** として相対化できる (「完全にする」expectation を下げる)
- 代わりに機械的制御 (§8) と subtraction trigger (§9.3) に投資する方が合理的と見える
- 「規約を完備する」という無限後退を避けて、acceptable failure rate を認める

### 9.5 Closed loop: 規約構造と Claude 応答構造の相互強化

規約ファイルは structured (表 / 箇条書き / セクション)。Claude の応答も structured (depth レイヤー / カテゴリ分類 / ランク付きオプション)。両者の構造が match すると、**相互強化ループ**を形成する:

1. Claude が structured 規約を読む
2. Claude が structured 応答を生成
3. User が structured 応答を見て structured な追記で規約を追加
4. Load 増加 → 古い規約が crowd out → 新違反
5. 1 に戻る

このループから出るには、片方が **unstructured に振る舞う必要**がある:

- User 側: 「今回は何もしない、受容する」を選択する局面を増やす (§9.1 triage の実運用)
- Claude 側: option list を生成せず 1 つの position だけ述べる局面を増やす (§9.7 参照)

### 9.6 Subtraction の形態: 削除 > migrate > 規約追加

違反への応答として自然に考えつく対応の好ましい順序:

| 対応 | コスト | 効果 | リスク |
|---|---|---|---|
| **削除**: 既存規約・memory・hook を除去 | 低 | load 減少 → 古い規約が活性化 | 情報損失 (git log で復旧可) |
| **Migrate**: 情報を別の場所に移動 | 中 | 同内容だが場所が変わる | accumulation が温存される / defer の一形態 |
| **規約追加**: 新ルールを書く | 中 | 新 cue を provide | 既存規約が crowd out、§9.5 ループを強化 |
| **Hook 追加**: 機械的制御を増やす | 高 | 該当状況で強制 | 誤検出、運用負荷増 |

**原則**: 違反を受けたとき、反射的に規約追加に向かわず、以下の順で検討する:

1. 既存の類似規約を **削除** (古くて違反されないルール、重複エントリ、毒 template)
2. 次善策として **migrate** (ただし「削除で済ませられないか」を必ず先に自問)
3. 既存規約で覆えない novel 失敗のみ **追加**
4. catastrophic 級のみ **hook 化**

**Migrate は defer の一形態** — 「とりあえず別の場所に動かした」は accumulation 温存であり、将来の棚卸しタスクを生む。削除で決着する選択肢を先に評価する。

### 9.7 Diminishing-returns detection と meta-loop 離脱 (Claude 側の規律)

LLM は「もっと深く」「もう一段」の push に対して resistance がない — 疲れない、飽きない、自尊心で突っぱねない。結果、**Claude 側から会話の diminishing returns を自発的に announce しないと meta-loop が収束しない**。また meta 議論が伸びるほど、**元のタスクから離脱した procrastination** になりやすい (規律改善の議論が本業を食う状態)。

Claude 側の規律 (work-discipline.md 相当):
- 同じ方向の push が 3 回連続 → 「diminishing returns かもしれません」と打診
- Meta 議論が元のタスクから 5 turn 以上離脱 → 「本線に戻りますか」と提案
- 「深く」系の push で生成された階層が 4 以上になったら、新規性 vs paraphrase を自己評価して honest に述べる
- Option list の生成を自動応答とせず、明確な position を 1 つ取ることを優先する
- 「何かアクションしないと」圧 (§8.5) を検出したら、**そのアクションが rule 追加 / memory 書き込みに向かっていないか** を一度立ち止まって確認

2026-04-17 session で実演: 6 turn の「深く」push に応えて Level 11 まで階層を生成、途中から paraphrase 成分が増加していたことを自己観察。次回は 3 turn 目で push-back を試みる運用。

---

### 9.8 単一観察から構造対策に飛ばない (scope 確認先行)

違反・不具合・ユーザー報告を受けた時、反射的に構造的対策 (新 rule / 新 hook / abstract framework) を設計する前に **現象の scope を確認する**。典型的な failure mode:

1 回の観察 → パターン仮説 → 構造対策の設計・実装 → 後から「実は scope 違い」が判明 → revert (実装コスト + 規約追加コスト + revert コスト + ユーザー説明コスト が全て無駄)。

**scope 確認の質問**: (a) 観察は独立した複数事例か 1 事例か? (b) ユーザーが継続的に直面する場面か偶発的か? (c) 対策の前提はユーザーの実運用に合致するか?

**適用例 (2026-04-17)**: odakin 環境で Haiku 使用時に日本語フォールバック観察 → 2 軸配置原則 (cross-machine × always-attention cell に CLAUDE.md inline が必要) を設計・実装 → odakin が「Haiku は一生使わない」と scope 確認 → 前提崩壊で全 revert。scope 確認を先行していれば対策設計も revert も不要だった。

§9.1 triage との組み合わせ: annoyance 級 × scope 不明 = **対策せず受容が基本**。material 級以上 × scope 確認済 = 対策設計へ。

---

## 10. File-role architecture — context 効率のための auto-load tier 設計

2026-04-17 の subtraction + compression session を経て抽象化した、cross-machine 規約システムの file 配置原則。LLM の session 冒頭 context 量が有限なので、**同じ情報量を保ちながら auto-load を削減する**設計。

### 10.1 4 tier 分類

| Tier | 性質 | 例 | auto-load? |
|---|---|---|---|
| **T0: harness auto-load** | session 冒頭に強制 load | `CLAUDE.md`, `MEMORY.md` | ✓ (全 session) |
| **T1: regulation table 必読** | 「必ず読む」指示が明示的 | `work-discipline.md`, `push-workflow.md` | ✓ (Claude が table 経由 active read) |
| **T2: regulation table 条件付き** | 特定 task 発生時のみ読む | `email-style.md`, `paper-style.md`, `user-profile.md` 等 | △ (task 関連時のみ) |
| **T3: pointer-only** | regulation table 不記載、pointer 経由 | `incidents.md`, `staging-incidents.md`, `leak-incidents.md`, 各 `DESIGN.md` | ✗ |

### 10.2 切り分け基準

「この content は毎 session 読まれる必要があるか?」を自問する:

- **rule 定義本体 / trigger 条件 / How to apply** → 必要 → T1 or T2
- **rule の supporting narrative (過去事例、具体 file path、exact sequence)** → 不要 → T3 に隔離
- **meta-procedure (ファイル追加手順、staging lifecycle 等)** → 不要 → T3 (DESIGN.md)
- **archive 目的の session log** → 不要 → T3 (日付付きファイル、規約 table 不記載)

### 10.3 narrative 抽出 pattern (T1 → T3)

T1 file が肥大化した時の救済 method:

1. 各 rule の「過去事例」block を T3 の narrative archive file に抽出 (chronological)
2. T1 側は 1 行 pointer に置換 (「詳細 → `<archive>.md` §YYYY-MM-DD」)
3. archive 側に「Related rules:」逆 link を置く

**例**: work-discipline.md の 4 過去事例 block (Memory gate / $-chat / 汎用原則 / Meta-loop) と push-workflow.md の 3 過去の失敗事例 を `odakin-prefs/incidents.md` に集約して T1 から pointer 化 (2026-04-17 実施、net -~40 lines T1 auto-load)。

### 10.4 失敗 pattern

- T0/T1 に narrative を詰めると context 圧迫 → autocompact 頻発 (2026-04-17 odakin 環境で実地観察、1 日で +468 lines T0/T1 拡大 → autocompact 頻度急増)
- T1 の rule 内に incident 詳細を embed すると後から T3 抽出に手間

### 10.5 Tier 間 lifecycle

content は tier 間を移動しうる。2026-04-17 odakin-prefs で観察された例:

- **T0 → T1**: MEMORY.md (T0) から work-discipline.md (T1) へ規律を移す (cross-machine 要件を満たすため、§5 参照)
- **T1 → T3**: narrative 抽出 (§10.3)
- **T1 内部 sub-tier**: rule 本体を T1 に残し、meta-procedure を `DESIGN.md` (T3) に移す

**incidents archive の 3-stage lifecycle** (odakin-prefs で実装):
`staging-incidents.md` (未結晶、2 件目待ち) → 結晶化 → `work-discipline.md` rule (T1) + narrative を `incidents.md` (T3) に移管。

### 10.6 適用例 (2026-04-17 odakin-prefs)

- T0: `CLAUDE.md` (125→108 lines)、`MEMORY.md` (100→41 lines)
- T1: `work-discipline.md` (268→321 lines、新規 7 rule 追加後に -40 の narrative 抽出)、`push-workflow.md` (87→85 lines、3 incident narrative 抽出後)
- T2: 既存 regulation table 配下 10+ ファイル
- T3 (新規): `incidents.md` (209 lines, 19 narratives)、`staging-incidents.md` (33 lines, 2 entries)、`DESIGN.md §2026-04-17 系 2 entries` (規約追加手順 + work-discipline.md 運用方針)

結果: T0+T1 auto-load 569 (pre-restructure 推定) → 555 lines (post-restructure)、T3 に ~600+ lines の narrative/meta を隔離保持 (情報損失なし)。

### 10.7 auto-context byte budget (行数 proxy からの脱却)

Tier 切り分けと並行で、**T0+T1 の byte 総量**を測定する。LLM context は token (≈ 4 bytes) で measured されるため、行数 threshold だけでは autocompact 頻度を説明できない。行数を満たしていても 1 行 あたりの密度が高いと context 消費は膨らみ、session 当たりの autocompact 回数を早める。

**観測指標** (参考値、環境により変動):
- T0+T1 合計 **50 KB 未満** → autocompact 稀
- T0+T1 合計 **100 KB 超** → 1 session 中に 1-2 回 autocompact
- 1 ファイル内 **line 当たり 200 bytes 超** → dense 化の疑い (descriptive / narrative が embedded)

**処置**: 行数 threshold を満たしているが autocompact 頻発する場合、**byte 密度** を疑い、§7.3 Description / Judgment 境界 + §10.3 narrative 抽出を実行する。inline 実装 how、変遷履歴、冗長な注記は判断文を残し DESIGN.md / T3 への pointer に delegate する。

**事例** (2026-04-18 LorentzArena 2+1): SESSION.md 94 行 / 23.8 KB (line density ~253 bytes) → 75 行 / 6.6 KB (line density ~88 bytes) へ圧縮。inline 実装詳細 (migration / ghost 物理統合 / worldLine 二分探索 etc.) を DESIGN.md 各節の pointer に delegate した結果、行数は -20% だが byte は -72%。CLAUDE.md も同系の dense 部 (ネットワーク migration detail、アーキ表 long cell、主要機能 bullets) を pointer 化して 371 → 357 行 / ~45 → ~36 KB。**line count threshold を守っていても byte で見ると context-heavy** という観測が §7.7 diagnostic の新 row を動機付けた。

**運用**: SESSION.md を書き足す時は `wc -c` で byte を即確認。8 KB 超過が見えたら dense row を pointer に差し戻す ( retroactive reorg ほど大掛かりでなく、その場で逆流を止める習慣で充分)。

### 10.8 削除・委譲判断の trap

tier 化 (§10.2) と byte budget (§10.7) で「どのファイルを減量するか」の方向性は見えるが、**どの行を削るか**の判断には系統的な失敗パターンがある。2026-04-18 の claude-config への §7 retroactive reorg 自己適用で抽出。

**Tier-direction asymmetry**: 委譲の効果は **tier の下り (T0→T1/T2、T1→T2/T3)** のみで発生する。T2→T2 や T3→T3 の横ずらしは auto-context bytes を減らさず、grep 手間だけ増やす ROI ゼロの作業。「file を分けると綺麗になる」という美意識で横ずらしに手を出すのは **autocompact 削減目的の文脈では anti-value**。委譲判断では先に「委譲先の tier が委譲元より低頻度か」を問う。

**T0/T1 chain pre-check**: T0 ファイルを圧縮する前に、T0 から link される T1 群が auto-context byte に含まれることを確認する。T0 の 1 行が dense な T1 表を指す pointer だった場合、T0 削減は総量 1 行分しか減らさない。**T0 の line count だけ見て判断すると miss する** — T1 の dense 行を pointer 化する方が ROI が高いケースが多い。

**Grep-substitute value**: auto-load された表 / 小辞典 / レジストリは Claude の session 内で **pre-computed grep cache** として機能する。削除/委譲すると、そのデータが欲しい時に `grep` / `Read` tool call が発生し、per-session tool invocation cost が増える。**auto-context byte の節約 vs session 当たり tool call 増加** を天秤に掛ける。「頻繁に参照される table」「description column が code に存在しない table」は auto-load のまま残すのが合理的。

**削除提案の self-correction** (2026-04-18 事例): LorentzArena 2+1/CLAUDE.md の ゲームパラメータ表 (87 行) を「`constants.ts` が正本なので参照置換で ROI 高い」と初期判断したが再評価で **anti-value** と結論。理由: (1) byte 節約は autocompact budget の 0.2% で不可視、(2) 説明 column は code に存在せず table 全体を崩さないと抽出不能、(3) grep-substitute 価値大 (constants.ts には numeric value のみで human-readable 説明が無い、per-session Read コスト発生)。**最初の ROI 判断は byte savings のみで grep cost と description column loss を見落としていた**。委譲判断では byte savings だけで決めず、使用頻度 × grep-substitute cost × description column 抽出可能性 の三方視点が必要。

**DESIGN.md 分割閾値** (§10 の派生指標): 単一 DESIGN.md が以下のいずれかを満たしたら分割検討:
- 2000 行超 / 150 KB 超
- domain が独立変化するようになった (例: 物理と描画が別 sub-project 化)
- `grep` で見出し anchor が曖昧になる (同名見出しが複数 domain に存在)
- **SESSION.md / CLAUDE.md などから DESIGN.md §X pointer が密集**していて session 冒頭に follow-read で丸ごと読まれがち — 行数が 2000 未満でも split で「session ごとに該当 domain 1 sub-file のみ read」にできれば効果大 (2026-04-18 LorentzArena 2+1/DESIGN.md 1371 行の split はこの基準で発動)

分割先の配置原則は §1 (影響範囲の最大公約数) + §10.2 (tier 維持)。分割は **一方向の decision** — 再結合は別の reorg event として扱うため、分割前に条件の複数を満たすまで保留する。

**Self-application discipline**: 規則を claude-config で定義する commit には、その規則を **claude-config 自身に同時 apply する pass** を含める。2026-04-15 に §7 (retroactive reorg) を定義、LorentzArena に 2 回適用 (2026-04-15 / 2026-04-18) したが claude-config DESIGN.md 自身への適用は 2026-04-18 まで遅延し、4 entries (symlink 化 / scrubbing 見送り / 自己言及的 odakin / EXPLORING 分離) が冗長に残存していた。**「規則を作ったリポが規則を守っていない」状態は self-consistency を損なう**。規約追加 commit では `-- claude-config/` に類似 pattern が残っていないか grep する工程を入れる。

---

### 10.9 Code を canonical とする doc dedup pattern (§10.8 と併読)

doc 側の table が code facts を duplicate している場合 (parameter 値 / TypeScript 型 / enum 等)、**canonical source は code**。doc は code への pointer を置くだけで、値や型の table は再掲しない。duplication は以下を招く:

- **drift risk**: code 更新時に doc 同期漏れ、値・型が食い違う
- **auto-context 浪費**: T0/T1 の auto-load doc に table が入っていると session ごとに token 消費

**⚠ §10.8「削除・委譲判断の trap」の warning を先に適用せよ**: description column が code (JSDoc 等) に存在せず doc 側にしかない場合、**dedup は anti-value**。byte 節約が 0.2% の invisible savings にしかならず、grep-substitute cache としての table 機能 + description の情報そのものを失う。2026-04-18 事例の LorentzArena パラメータ表は §10.8 で anti-value と判定されているにもかかわらず、後続の Level-2 migration (commit `cb3ca94`) で削除実行された。**constants.ts の JSDoc coverage を確認せずに削除すると情報損失**。

**安全に適用できる場面** (§10.8 warning を通過する場合):
- code 側に JSDoc / inline comment が充実しており description column の再現が不要
- table の grep-substitute 利用頻度が低い (session ごとに一度も参照されない)
- byte savings が 5% 以上の有意な減量

**pattern** (warning 通過後):
- 値・型の table を doc から削除
- 「canonical は `src/X.ts` (JSDoc + section コメントで分類)」という 2 行 pointer に置換
- category 名リストが必要な時は値なしで列挙

**2026-04-18 LorentzArena**: 2+1/CLAUDE.md から Parameters table (80 行) を削除し `constants.ts` pointer に移行。**§10.8 の事例が示すように初期 ROI 判断は再検討対象**。次 session で constants.ts の JSDoc 網羅性を確認し、description column が失われているなら docs/architecture.md に restore する判断が必要。

### 10.10 CLAUDE.md chain の nested auto-load (Claude Code 実装依存)

Claude Code は CWD から上向きに `CLAUDE.md` chain を全て auto-load する。sub-project で作業する場合、例えば CWD = `~/Claude/LorentzArena/2+1/` なら:

- `~/Claude/CLAUDE.md` (user-level、通常 symlink to personal prefs)
- `~/Claude/LorentzArena/CLAUDE.md` (repo root)
- `~/Claude/LorentzArena/2+1/CLAUDE.md` (sub-project)

の**全てが 1 session の session-start context に入る**。chain の合計サイズが dominant component になりやすく、sub-project の CLAUDE.md が大きいと autocompact 頻発。

**対策**:
- 各層を role-limited に保つ (user-level = 全体規約 table、repo root = リポ overview、sub-project = 固有 orientation)
- sub-project CLAUDE.md は commands + preview quirks + architecture 超要約 + pointers の ~80–100 行に収める
- 詳細は同階層の `docs/` 配下に置き (T3)、CLAUDE.md から pointer

**2026-04-18 LorentzArena 実証**: `2+1/CLAUDE.md` 364 → 97 (-267 lines)、chain 全体 505 → 238 (-267)。

### 10.11 「超要約 (super-summary)」pattern

slim 化した CLAUDE.md には「アーキテクチャ超要約」section を 1 つ置く。**5-8 項目 × 1 行 (+ 詳細は `docs/architecture.md §X` pointer)** で session 冒頭に orientation を確実に供給。

**効果**: pointer を辿らない session (軽 task / 小モデル / 慣性で素通り) でも、主要 dimension (rendering / physics / network / state / message / parameters 等) の 1 行要約は context に入る。「詳細は辿って、全体像は inline」の 2 層化。

**設計基準**:
- 各行は後続の詳細読みの entry point として働く (キーワード + 1 文)
- 具体値・table は禁止 (それは code/docs 側の仕事)
- 超要約だけで session が成立する task (軽い修正、定型作業) がある程度カバーできること

**例** (2026-04-18 LorentzArena 2+1/CLAUDE.md §アーキテクチャ超要約): 描画 / 物理 / ネットワーク / State / Message / Parameters の 6 項目、各 1-2 行 + 詳細 pointer。

### 10.12 Migration level の階段

単発ではなく**多段階 migration** として構造化すると健全:

| Level | target | 典型的な savings |
|---|---|---|
| **Level 0**: cleanup | 削除 + memory 整理 (§9.6 subtraction order) | 数十 lines |
| **Level 1**: dense content → DESIGN.md pointer 化 | CLAUDE.md 内部で重い節を pointer へ置換、DESIGN.md は auto-load 外 | ~100 lines |
| **Level 2**: reference content → docs/ 分離 + code canonical | architecture / params / schema を `docs/architecture.md` + code pointer に | 数百 lines |
| **Level 3**: task-specific docs を最小化 | T2 regulation files (email-style.md 等) の重複排除 | 十〜数十 lines |

各 level は独立に実施可。下の level ほど radical で savings 大きい。**対象 CLAUDE.md が 300+ 行で session 立ち上げ速度が体感悪化しているなら Level 2 が費用対効果最高**。

---

## 11. In-plan exploration trail — single-session walkback の保存

§6 で establish した DESIGN.md / EXPLORING.md 分離は **cross-session 探索** (= EXPLORING にエントリを残し、 後で結晶したら DESIGN に promote) を扱う。 これとは別軸で、 **同 session 内で plan が iteration を経て複数案を撤回しながら最終決定に着地する** ケースの content保全 pattern を 2026-05-06 LorentzArena NPC 非対称 plan で抽出。

### 11.1 問題: walkback の trail が plan close 時に消える

長 session で plan を立てて iterate するとき、 以下の dynamics が起こる:

1. 初期提案 (= A 案) を起こす
2. user feedback で問題発覚、 修正案 (= B 案) を提案
3. B 案を実装する形で plan を rewrite (= A 案の文章を上書き)
4. 更に iterate して B も撤回、 C 案で最終確定
5. plan を close

このとき plan には C 案だけが残り、 **A → B → C の walkback trail が消える**。 しかし trail こそが「なぜ C なのか」 の理解に必要 — 後の reader が「A や B はなぜダメだったのか?」 を再質問する元手になる情報が失われている。

### 11.2 §6 EXPLORING.md との違い

§6 は **「未決定の探索」 を DESIGN.md と分離**するため EXPLORING.md を作る pattern。 探索が結晶したら DESIGN.md に promote、 古い候補は消す。

本節 §11 は **「決定済 plan 内の walkback 保存」** で、 plan は decision form で close するが decision に至るまでの撤回経緯を残したい。 EXPLORING.md には行かない (= もう探索じゃない、 plan は close する) し、 plan 本体に trail を埋め込む。

### 11.3 解決: plan §1.6 etc. に「探索過程」 セクションを置く

plan の §1 (= 思想・前提) の subsection (例: §1.6 「探索過程」) に、 session 内 iteration の trail を時系列で記録:

```markdown
### §1.6 探索過程 (= YYYY-MM-DD session 内の back-and-forth)

「なぜ <最終案> に着地したか」 を後の reader が再現できるよう、 探索の back-and-forth を記録。

**探索 0 (= 出発点)**: <初期提案、 動機>。 → <この insight は終始一貫して採用された / 撤回された >

**探索 1 (= <発見の名前>)**: <修正案、 framing>

**(<撤回案>) の撤回**: <撤回理由、 false premise なら明示>

**探索 2**: ...

**探索 N (= 最終形)**: <着地>。 要素分解:
- A 軸 = ...
- B 軸 = ...

**思想 trail の core**:
> <最終案を導出する N つの insight の統合 framing>
```

### 11.4 適用判断: いつ §1.6 を書くか

trail 保存に値するのは「**撤回された案が plan close 時点でも反省的価値を持つ**」 場合のみ:

- ✓ **書くべき**: false premise で撤回された案 (= 後の reader が同じ premise で同じ案を再提案する risk)、 user-side の structural insight で撤回された案 (= why の部分が valuable)、 「(α)/(β)/(γ)」 のような複数候補から 1 つに絞った経緯
- ✗ **書かない**: 単純な typo / 計算ミス修正、 user の好みの変更だけ、 探索過程と関係ない実装 bug

**rule of thumb**: plan close 時に「`§11 やらないこと` に rejected proposal を追加するか?」 と問う。 追加するなら §1.6 にも探索の trail を残すと整合的 (= rejected proposal の rationale が trail に紐づく)。

### 11.5 §11 「やらないこと」 との関係

plan の §11 「やらないこと」 (= rejected alternatives + 却下根拠 + 将来再開 trigger) は **decision-form の rejection 記録**。 §1.6 探索過程は **process-form の trail**。 両者は重複しない:

- §11.X: 「✗ <案>: 主張案 = ...、 却下根拠 = ...、 将来再開 trigger = ...」 (decision)
- §1.6: 「探索 N で <案> を提案、 <発見> で撤回」 (process)

§11 だけだと「却下根拠は分かるが、 そもそもなぜ提案されたのか?」 が見えない。 §1.6 だけだと「将来また同じ案が出たらどう判断するか?」 の re-decision 材料がない。 両方あって初めて「**なぜ提案されたか + なぜ却下されたか + 将来再開条件**」 が一貫した narrative として読める。

### 11.6 適用事例

- **2026-05-06 LorentzArena NPC 非対称 causality plan** ([`plans/2026-05-06-npc-asymmetric-causality.md`](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-npc-asymmetric-causality.md) §1.6): user の Bug 14 propagation race 議論からの分岐で、 (I) NPC 非対称 → (II) dead = 死亡時時空点 → (II'') dead-skip 完成 → (II''') mean formula + self 包含 の 4 案を経て (II)/(II'') の 2 段 walkback で (I) + (II''') + (III) に着地。 (II)/(II'') 撤回理由 (= false premise 発見、 user の structural insight) を §1.6 に記録、 §11.12 「やらないこと」 に対応する decision-form rejection と紐づけ。 後の reader が plan を読むだけで「なぜ §1 が dead を virtualPos で寄与させる framing なのか」 を再構築できる

---

## 12. 監視 list の scope marker — 「監視」 と「禁止」 の categorical 分離

### 12.1 観察された pathology

DESIGN.md / 設計 docs で「**drift 監視のため定期 re-grep 推奨**」 のような **list 形 audit checklist** を運用していると、 list が implicit な scope を持って blind spot を生むことがある。

具体例: list の entry が全て「docs (= CONVENTIONS.md / conventions/*.md)」 に偏っていて、 「scripts / hooks / setup.sh 等の executable surface」 が暗黙のうちに対象外扱いされる経路。 list の前文には「定期 re-grep」 とあるだけで、 (a) 何の category を対象に grep するか、 (b) 何が categorically 対象外か、 が明示されていない。 結果: 同 class の violation が executable surface に蓄積、 「list で監視しているから大丈夫」 という錯覚で audit が skip される。

### 12.2 「監視」 と「禁止」 の categorical 分離

ある violation class に対して、 surface ごとに対処レベルが異なる場合がある:

- **監視** (= soft、 list-based、 doc 内手作業 grep): **意図的に許容している記述** に適用、 drift 検出は人手 / scheduled-task で行う
- **禁止** (= hard、 mechanism-enforced): hook / pre-commit / regex / CI で機械的に block、 violation は merge されない

両者は categorical に分離されるべきで、 同 list に混在させると論理が壊れる。 例えば「docs 内の odakin 名言及」 は 「監視」 (= 意図的に置いている、 削除トリガー で発火)、 「executable code 内の odakin 名言及」 は 「禁止」 (= layer-1 audience contract 違反、 即修復対象)。

### 12.3 解法: explicit scope marker を必須化

監視 / audit list を書くときは、 list の前文または冒頭 row に **explicit scope marker** を含める:

| 要素 | 例 |
|---|---|
| **対象 surface の enumeration** | 「本 list は CONVENTIONS.md と conventions/*.md (= **docs**) 内の意図的記述のみ対象」 |
| **categorically 除外される surface の enumeration** | 「scripts/, hooks/, setup.sh 等の **executable code** は本 list ではなく即修復対象」 |
| **除外理由** | 「executable は foreign user の machine で実行されるため、 audience contract 違反は監視ではなく禁止」 |
| **境界条件で迷ったら何をするか** | 「迷ったら本 list ではなく hook / pre-commit に投げて mechanism 化」 |

scope marker は **list の機能の一部**。 marker 無しの list は「実は何を監視しているか暗黙」 で、 数か月後の reader が誤って scope 外も含むと解釈する経路を持つ。

### 12.4 由来

2026-05-10 claude-config self-audit で `DESIGN.md §「自己言及的 odakin 記述」` list (= 4 entries の docs 監視 list) が hooks / scripts / setup.sh の同 class violation を見逃したケース。 list 自身は「drift 監視のため定期 re-grep 推奨」 と書いてあったが、 暗黙 scope = docs のみだったため、 同 session の `hooks/memory-guard*.sh` の `odakin-prefs/` literal は list に登録されておらず、 final cross-cutting sweep で初めて発見された。 修復として list 前文に explicit scope marker を追加 (= claude-config commit `e3179c5`)、 「executable code 内の literal は本表ではなく即修復対象 (= 監視ではなく禁止)」 を categorical に明示。

### 12.5 適用範囲

- audit / drift / monitoring / re-grep / track と書かれた list 全般
- list が複数 surface (= docs + code + config 等) にまたがる候補 violation の subset を扱う場合
- 「意図的記述」 と 「bug」 を同 class violation で区別する必要があるとき (= surface 別に対処レベルが異なる typical case)

### 12.6 周辺規律

- §3 「規約追加の判断基準」 の延長: list の scope を明示しないのは「規約があるが読まれない」 の典型 pathology
- [`conventions/debugging-discipline.md §4`](../conventions/debugging-discipline.md) (sibling audit) の前提: scope が明示されていない list は sibling 漏れの源、 sweep が補完
- §10 File-role architecture: 監視 list (= soft、 cold reference) と禁止 (= hook、 always-on enforcement) は categorical に異なる surface に置かれる

---

## 13. Cross-repo refactor の migration ordering — データ側を先に commit

### 13.1 観察された footgun

複数 repo (= 同一 owner の cross-repo、 cross-layer、 collaborator-shared 含む) を跨いで refactor する場合、 commit / push の順序によって時間窓 (= time window) で意図しない state が出現する。

具体例: claude-config の `setup.sh` が個人層 (= layer 3、 別 repo) の `secrets-repos.txt` を read するように refactor する場合:

- **逆順 (= claude-config 先 → 個人層 後)**: claude-config push 時点で新 setup.sh は `<personal-layer>/secrets-repos.txt` を read しようとする → file 不在 → graceful skip でないと regression。 個人層 push 後に file が出現 → 次 setup.sh 起動から正常動作
- **正順 (= 個人層 先 → claude-config 後)**: 個人層 push 時点で file 存在、 claude-config 旧 setup.sh は file を read しないので影響無し。 claude-config push 後 setup.sh が新 logic で file を read → 正常動作

両順序とも graceful skip 設計なら functional regression は無いが、 正順は「想定外動作期間」 を最小化する。

### 13.2 原則: データ側を先に commit、 コード側を後に commit

cross-repo refactor で 「repo A のコードが repo B のデータを read する」 形になる場合、 **B を先 / A を後** で push する:

| 役割 | 例 | 先後 |
|---|---|---|
| **データ側 (= 受動側)** | 個人層 / config registry / lookup table / 共通 fixture | **先** push |
| **コード側 (= 能動側)** | bootstrap script / runtime reader / consumer | **後** push |

### 13.3 graceful skip 設計の併用

正順だけで footgun は減るが、 完全に防ぐには **コード側を graceful skip 設計** にする (= データが無くても crash せず空 array / no-op で続行)。 これにより:

- 逆順でも functional regression なし
- 一時的にデータが消えた / 移動した場合も resilient
- foreign user (= データを持たない user) で動作

graceful skip + 正順 push の組み合わせで、 (a) 想定外動作期間最小化、 (b) edge case の resilience 両方を確保。 graceful skip 単独では「想定外動作期間に skip が走って setup が無音失敗」 という silent regression 経路が残るため、 慣例としての正順 push は依然必要。

### 13.4 collaborator-shared 場合

repo A と repo B が別 maintainer の場合、 atomic な順序確保はできない (= 両 maintainer の協調が要る)。 戦略:

1. **データ側 maintainer に先行 push を依頼**、 完了確認後にコード側 maintainer が push
2. **graceful skip を必須化**: atomic でない時間窓は graceful skip で吸収、 monitoring (= run-time error log / alert) で異常検出
3. **window 最小化**: 両 push の間隔をできるだけ詰める (= 同 day / 同 hour)

multi-maintainer の場合、 順序保証よりも graceful skip の方が defensive。 順序は best effort、 設計は worst case 想定。

### 13.5 由来

2026-05-10 claude-config self-audit で `setup.sh:863` の `SECRETS_REPOS` runtime hardcode (= 所属機関名を含む repo 名を含み CLAUDE.md L105 違反) を個人層 `secrets-repos.txt` 外出しに refactor した際、 `odakin-prefs` commit `b62bb7d` (= データ側) を先行 commit、 `claude-config` commit `13eba10` (= コード側) を後 commit で進めた事例。 graceful skip も併用 (= LAYER 空 / file 不在で `SECRETS_REPOS=()`) しているため、 仮に逆順でも functional regression は発生しないが、 慣例として正順を採用することで「想定外動作期間 = 0」 を達成。

### 13.6 適用範囲

- 同一 owner の cross-repo refactor (= 4 層 cross-layer 含む)
- collaborator-shared repo 間の refactor (= layer 2 内の repo 間 + layer 1↔2 等)
- monorepo 内でも build artifact / generated file を生む build 段の順序

データを read する code が新規導入される場合の汎用 pattern。 read される data が既に存在する code を変更するだけなら本原則は適用外。

### 13.7 周辺規律

- §2 「ルールの重複を避ける」 の延長: data 側を canonical とし code 側は読み取り経路 (= ポインタ) として 1 ファイル定義
- [`conventions/shared-repo.md §「公開前の Audit」`](../conventions/shared-repo.md): collaborator-shared repo の commit 規律
- 関連 anti-pattern: 1 commit に複数 repo の変更を atomic に詰めようとする (= sub-tree merge / 提出物分散) は coordination overhead と review 困難を招く、 順序 + graceful skip の方が単純

---

## 14. 大規模 reference / gotcha convention の intra-file 構造 — slug identity + 検証可能 index

§10 (File-role architecture) は **file 間**の auto-load tier 配置を扱う。 本節はその裏の concern = **単一 convention が大きくなった時の file 内部構造**。 落とし穴集・reference 集のように「1 file に多数の独立 entry が貯まる」 convention が肥大すると、 §10 の tier 移動とは別の保守 pathology が現れる。

### 14.1 trigger signal (= 3 つのいずれか)

- **(a) サブセクション過多**: `###` が数十に達し、 flat namespace で navigation / 重複検出が困難
- **(b) letter-suffix 番号の増殖**: positional 番号 (`§2-4`) が満杯になり、 中間挿入のたびに接尾辞 (`§2-4b`) が増える = **番号が「位置」 に identity を縛っている**証拠
- **(c) 機械検証できない cross-ref 網**: 内部 §-ref が手 join で、 dangling / 重複が人手 sweep でしか見つからない

1 つでも該当したら identity を**位置非依存**にする。

### 14.2 cross-ref は positional 番号でなく安定 slug で

各 entry に kebab-case の安定 slug を与え、 cross-ref を slug で書く (= markdown なら `<a id="slug">` anchor + `[`slug`](#slug)` link)。 利得: 挿入・並べ替え・**ファイル移動**で ref が壊れない、 semantic (番号より意味が読める)、 **validator で dangling 検出可能**。 旧 positional 番号は捨てるが、 他 doc の dated/historical 参照が解決し続けるよう **index に `legacy` として保存**する (= 番号の identity でなく解決可能性だけ残す)。

### 14.3 薄い index で「DB の利点」 を prose を動かさず得る

「entry が多い → DB 化したい」 直感の**正しい翻訳**は、 prose を yaml に移すことではない (= markdown-in-yaml は編集性を殺す + LLM consumer は grep で十分読める)。 **本文 prose は markdown のまま**、 別ファイルの薄い index (= `id` / `legacy` / `title` / `related` のメタだけ) で「join 検証 + 重複 surface」 という DB の利点だけを取る。 validator が (1) 全 ref が解決 (dangling 0)、 (2) 見出し ↔ index が全単射 (orphan 0)、 (3) 重複候補を keyword overlap で surface、 を機械化する。 ⚠️ prose を yaml に移すのは anti-pattern (= §2 の「定義は 1 箇所」 を index 側に誤適用しない、 prose が定義本体)。

### 14.4 split-axis は access pattern に合わせる + slug を先に振る

肥大 convention を将来 file 分割するなら、 **何の軸で割るかは「何で引かれるか」 で決める**:

- recency 軸 (hot/cold): 古い entry が滅多に参照されない場合 (= 個人層の作業規律 doc を hot file + grep 専用 archive に割った例)
- **topic / concern 軸**: entry が「踏んだ症状の種類」 で引かれる場合 (= 本 repo の office-automation.md は xlsx / docx / pdf / form-discipline で割るのが適)

🔑 **enabling insight = slug を先に振れば分割は ref-safe**: slug は identity を「位置」 からも「ファイル」 からも切り離す。 → **slug 化を先にやれば、 後続の topic 分割は ref を一切壊さない無痛操作**になる (= entry をどの file に動かしても slug ref は有効)。 だから順序は必ず **slug → 分割**。 分割自体は navigation pain が実証されてからで良い (= reading は grep で困らない、 §9.8 過剰対策の回避)。

### 14.5 mechanical な部分は script 化 (§10.9 と整合)

reference convention 内の「反復実行・検証用の手順」 は illustrative な code 片のまま貯めず script に抽出し、 prose は薄い why/when + script pointer に寄せる (= §10.9 code-as-canonical の reference-convention 版)。 validator 自体もこの一例 (= 整合性検証を prose の「手で sweep せよ」 規律から決定論 script に移す)。

### 14.6 由来 + worked example

2 つの観察から一般化 (= §9.8 「単一観察から飛ばない」 を満たす、 観察は 2 件):
- 個人層の作業規律 doc の **recency 軸 hot/cold 分割** (archive-first restructure)
- 本 repo `conventions/office-automation.md` の **slug 化 + index + validator** (= positional §-番号が letter-suffix 6 個まで増殖 + 内部 ref が無検証だった 1300+ 行 file を、 識別子だけ位置非依存化。 topic 分割は ref-safe になった状態で defer)。 worked artifact: `conventions/office-automation.index.yaml` + `scripts/check-office-automation-index.py`。

決定的動機: 検証系 entry を追記した際、 それが既存 entry の mandate を掘り崩す regression を、 **機械検証が無いため手の多軸 sweep で初めて発見**した (= dangling / contradiction 検出が人手依存)。 数十 entry 規模でこれは破綻するため、 整合性検証を script 化する。

---

## 変更履歴

| 日付 | 変更 | 動機 |
|------|------|------|
| 2026-04-02 | 初版作成 | 武貞メール対応での8件の不手際を分析し、規約設計の原則を抽出 |
| 2026-04-03 | §3 の適用事例追加 | push 連鎖障害: 「規約はあるが手順が不明確」→ CONVENTIONS §3 に粒度・障害対応を追加、教訓の詳細は email-office DESIGN.md に記録 |
| 2026-04-06 | §6 追加: DESIGN.md と EXPLORING.md の分離 | LorentzArena 2+1 の DESIGN.md 肥大化 + スマホ UI 思考メモの記録先問題。3 カテゴリ（決定 / 探索 / メタ決定）の分析を経て、決定と探索を 2 ファイルに分離する convention を導入 |
| 2026-04-15 | §7 追加: 決定後の content lifecycle と DESIGN.md の肥大化対策 | LorentzArena 2+1 の DESIGN.md が 1186 行まで肥大化 (Authority 解体リファクタで 8 entry が supersede、各 entry に ※ 注釈で本文温存) した問題を整理する過程で抽出。5 分類 (ACTIVE / DEFER / SP / SX / LESSON)、完了リファクタ集約 pattern、LESSON 集約用「メタ原則」セクション pattern、サイズ閾値を導入 |
| 2026-04-15 | §7 v2 化 + §2 に snapshot 原理を establish | 初版 §7 を書いた直後の深化議論で (1) day 1 ルールと retroactive 救済の混在、(2) archive vs snapshot の解釈曖昧、(3) Description と Judgment の境界未定義、を検出。§2 preamble に snapshot 原理を明示し §6/§7 をその application として位置付け。§7 を 3 分類 (ACTIVE/DEFER/LESSON) + transient 超越処理に簡素化、Description/Judgment 境界と粒度ルールを追加、When-in-doubt default を整理 |
| 2026-04-17 | §5 改訂 + §8・§9 追加 | git pull 忘れの annoyance 失敗への反射応答で memory に feedback を書こうとした違反を契機に、規約システム全体の subtraction pass。§5 (メモリ) をマシン固有事実のみに narrow 化し memory-guard hook を `ask` → `deny` 化。§8 で rule vs mechanism 非対称性・precedent-as-training-data・friction asymmetry を言語化。§9 で triage (catastrophic/material/annoyance)・asymmetric reflection bias・subtraction trigger・preference-approximation gap・Claude 側 diminishing-returns detection を整理。適用事例は odakin-prefs 2026-04-17 の commit 群 (git log) |
| 2026-04-17 | §8.5-8.7 + §9.5-9.7 追加 (coverage sweep) | 同日 session で session log に記録されていたが claude-config 側に無かった洞察を補完: §8.5 不安応答としての memory write、§8.6 agent 学習の錯覚 (correction は session 越えて persist しない、system 改変のみ残る)、§9.5 規約構造と Claude 応答の closed loop、§9.6 subtraction 形態 (削除 > migrate > 規約追加) + migrate-as-defer 警告 |
| 2026-04-17 | §9.8 追加 + §10 新設 (final sweep) | 同日 session の未捕捉 insight 2 件を durable 化: §9.8 単一観察から構造対策に飛ばない (Haiku false positive の lesson を一般化、scope 確認先行)、§10 File-role architecture (auto-load tier 0-3 分類、narrative 抽出 pattern、incidents archive lifecycle)。odakin-prefs での実証値も収録 (569 → 555 lines auto-load、T3 に 600+ lines 隔離) |
| 2026-05-10 | §12 追加 (監視 list の scope marker) + §13 追加 (Cross-repo refactor の migration ordering) | claude-config self-audit (= memory-guard hook の `odakin-prefs/` literal 1 件発見 → 全 hooks + 全 scripts + setup.sh sweep で sibling 20+ 件発見) で得た 2 件の universal 知見を durable 化。 §12 は DESIGN.md drift 監視 list が executable surface の同 class violation を見逃した経験から (= 暗黙 scope の blind spot)。 §13 は setup.sh の SECRETS_REPOS 個人層外出し refactor で odakin-prefs 先 / claude-config 後で push した順序確立から。 詳細 commit chain: claude-config `60a58c0` 〜 `13eba10` + odakin-prefs `b62bb7d` |
| 2026-04-18 | §10.9-10.12 追加 (Level-2 migration insights、§10.7-10.8 の後) | 他 session が先に追加した §10.7 byte budget + §10.8 削除・委譲の trap の後に追記 (section 番号 collision を避けて renumber)。LorentzArena 2+1/CLAUDE.md の radical delegation (364 → 97 lines) から抽出: §10.9 code を canonical とする doc dedup (ただし §10.8 warning を先に適用 — description column が code に無ければ dedup は anti-value)、§10.10 CLAUDE.md chain の nested auto-load (Claude Code 特有、sub-project で chain が積み上がる)、§10.11 「超要約」pattern (slim CLAUDE.md に 5-8 項目×1行の 2 層化)、§10.12 migration level 階段 (Level 0-3)。LorentzArena chain 505 → 238 lines の実証値。**本追記中の §10.9 LorentzArena パラメータ削除は §10.8 の anti-value 判定と衝突、次 session で constants.ts JSDoc 確認 + 必要なら docs/architecture.md に restore の要あり** |
| 2026-04-18 | §7.7 に byte-density row + §7.8 に 2 回目適用 + §10.7 新設 | LorentzArena 2+1 の 2 回目 retroactive reorg (DESIGN.md 1627→1303 行) で、SESSION.md が 80 行 threshold 内 (94 行) なのに 23.8 KB と重く autocompact を早める事象を観測。line count は proxy に過ぎず token 消費は byte に従うという lesson を §10.7 auto-context byte budget として規約化 (50 KB / 100 KB / 200 bytes/line の観測指標 + 処置 + SESSION.md 23.8→6.6 KB 事例)。§7.7 diagnostic table に「行数 threshold 内だが byte 密度高い」row、§7.8 適用事例に 2 回目適用段落を追記 |
| 2026-04-18 | §1 に bundle rule (pragmatic relaxation) 追加 | claude-config DESIGN.md 自身への §7 初適用 (規則を定義したリポに規則を適用する self-consistency 回復) で、`~/Claude/CLAUDE.md` 解体時の bundle 判断 (「1 rule = 1 file 厳格適用は 1 行ファイルを生む、関連密接かつ合計 10 行未満は bundle 可」) を §1 の corollary として昇格。配置先は影響範囲の最大公約数に従う原則は保持したまま粒度の下限を緩和 |
| 2026-04-18 | §10.8 新設「削除・委譲判断の trap」+ §7.8 に 3 回目適用 | claude-config への §7 自己適用 session で抽出した 6 件の insight を §10.8 に集約: tier-direction asymmetry (横ずらし委譲は ROI ゼロ) / T0-T1 chain pre-check / grep-substitute value (auto-load 表は pre-computed grep cache) / 削除提案 self-correction 事例 (LorentzArena ゲームパラメータ表 anti-value 判定) / DESIGN.md 分割閾値 / self-application discipline (規則定義リポへの同時 apply pass)。§7.8 に 3 回目適用段落で cross-domain validation (物理/描画 + 規約/メタ) を記録 |
| 2026-05-06 | §11 新設「In-plan exploration trail」 | LorentzArena NPC 非対称 plan で (II)/(II'') の walkback を経て (II''') に着地。 §6 EXPLORING.md は cross-session 探索用、 本 §11 は same-session 内 plan の back-and-forth trail を §1.6 「探索過程」 として plan 本体に保存する pattern。 §11 「やらないこと」 (decision-form) と §1.6 探索過程 (process-form) は重複せず補完、 両者揃って初めて rejected alternative の「なぜ提案 / なぜ却下 / 将来再開条件」 が一貫した narrative として読める |
| 2026-06-05 | §14 新設「大規模 reference / gotcha convention の intra-file 構造」 | office-automation.md (1300+ 行 / 69 サブセクション / letter-suffix § 6 個 / 無検証の内部 ref 網) の slug 化 restructure から抽出。 §10 が file 間 tier を扱うのに対し §14 は単一肥大 convention の file 内部 = 別 concern。 trigger 3 signal (サブセクション過多 / letter-suffix 増殖 / 無検証 cross-ref) + slug identity (legacy は index に保存) + 薄い index で DB 利点 (prose は yaml 化しない) + split-axis を access pattern に合わせる (recency 軸 = 作業規律 doc / topic 軸 = office-automation) + slug-first で分割 ref-safe + mechanical は script 化。 2 観察からの一般化 (§9.8 充足) |

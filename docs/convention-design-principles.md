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

メモリ（~/.claude/projects/...）はローカル限定であり、他端末・他セッションからは見えない。

**メモリに置くべきもの:**
- フィードバック（行動矯正） — autocompact 後の自分への申し送り
- クイックリファレンス — 正本はリポにあるが、頻繁に参照する情報のキャッシュ
- ユーザー情報 — 対話スタイルの調整に使う情報

**メモリに置くべきでないもの:**
- ルールの定義 — 他端末で再発する
- プロジェクトの正本情報 — リポの CLAUDE.md / SESSION.md に書く
- コードの構造やパターン — コードを読めば分かる

**メモリとリポの関係:** メモリはリポの規約を「補強」するが「代替」しない。メモリが消えてもリポの規約だけで正しく動作できる状態が正。

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

**self-consistency**: §7 自身が **LESSON の一例** である。LorentzArena の肥大化を観察 → 「超越 content の lifecycle を規律化すれば肥大化は防げる」という横断原則を抽出 → §7 として一般化。この `convention-design-principles.md` 自体が「§ メタ原則」を持つ DESIGN.md 相当の文書であり、§7 は自身が snapshot 原理に従う entry として書かれている。

---

## 変更履歴

| 日付 | 変更 | 動機 |
|------|------|------|
| 2026-04-02 | 初版作成 | 武貞メール対応での8件の不手際を分析し、規約設計の原則を抽出 |
| 2026-04-03 | §3 の適用事例追加 | push 連鎖障害: 「規約はあるが手順が不明確」→ CONVENTIONS §3 に粒度・障害対応を追加、教訓の詳細は email-office DESIGN.md に記録 |
| 2026-04-06 | §6 追加: DESIGN.md と EXPLORING.md の分離 | LorentzArena 2+1 の DESIGN.md 肥大化 + スマホ UI 思考メモの記録先問題。3 カテゴリ（決定 / 探索 / メタ決定）の分析を経て、決定と探索を 2 ファイルに分離する convention を導入 |
| 2026-04-15 | §7 追加: 決定後の content lifecycle と DESIGN.md の肥大化対策 | LorentzArena 2+1 の DESIGN.md が 1186 行まで肥大化 (Authority 解体リファクタで 8 entry が supersede、各 entry に ※ 注釈で本文温存) した問題を整理する過程で抽出。5 分類 (ACTIVE / DEFER / SP / SX / LESSON)、完了リファクタ集約 pattern、LESSON 集約用「メタ原則」セクション pattern、サイズ閾値を導入 |
| 2026-04-15 | §7 v2 化 + §2 に snapshot 原理を establish | 初版 §7 を書いた直後の深化議論で (1) day 1 ルールと retroactive 救済の混在、(2) archive vs snapshot の解釈曖昧、(3) Description と Judgment の境界未定義、を検出。§2 preamble に snapshot 原理を明示し §6/§7 をその application として位置付け。§7 を 3 分類 (ACTIVE/DEFER/LESSON) + transient 超越処理に簡素化、Description/Judgment 境界と粒度ルールを追加、When-in-doubt default を整理 |

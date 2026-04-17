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

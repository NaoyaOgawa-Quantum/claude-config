# Debugging discipline

Bug fix 提案を 「root だ」 と確信する前に通すべき audit と、 fix 採択後の drift 防止規律。 Claude が fix 提案を生成する際の reflex として universal applicable。

LorentzArena Bug 14 完全治療 (2026-05-06) の spiral で複数の fail-recover round を経験した経緯から、 odakin-prefs/work-discipline.md にあった odakin-specific 規律のうち universal な核を抽出 promote。

---

## 1. Fix 提案の 3 verification (= L4-L5 + numeric trace + code coverage)

**ルール**: fix 提案を 「root だ」 と確信する前に **3 verification** を全て通す。 全 pass まで commit / approval / 「root 確定」 NG。

| # | Verification | 内容 |
|---|---|---|
| **V1 (semantic + numeric)** | Semantic / scenario trace | L4 (= 概念モデル / 設計柱と矛盾なし) + L5 (= 数値解析的安定性 / 不変条件) で root を identify、 全 case scenario で実数値 / 状態 trace、 corner case 破綻 (= over/under count、 race、 boundary 不整合) が無いか |
| **V2 (code coverage)** | 「既存が handle 済」 主張 verify | pattern match で済まさず **actual code を読んで scenario trace で coverage 確認**、 grep + 関数 read + walk-through で想定 path = actual path を confirm |
| **V3 (algorithm enumeration、 L5 fix のみ)** | 代替 algorithm 網羅 | L5 fix で「substep / cap / clamp」 系 workaround を提案したら、 **代替 algorithm 全列挙** (= explicit / implicit / analytic / symplectic / RK4 / substep) して 1st choice の正当性 confirm。 線形 ODE は通常 closed-form で解ける、 substep は workaround で root ではない (= 詳細: [`scientific-computing.md §2`](scientific-computing.md)) |

「conceptually clean」 「既存 mechanism handle するはず」 はいずれも **未検証の仮説**、 user / 自己が「ad hoc 感」 を覚えたら 3 verification を反射的に走らせる trigger。

### 自己 audit signal (= 絆創膏 sign 早期検知)

提案 fix が下記のどれかの形をしていたら絆創膏 sign:

- 「**...if X > threshold then truncate / clamp**」 (= cap 系絆創膏)
- 「**...add Y listener to catch X case**」 (= listener 系絆創膏)
- 「**...reset state on Y event**」 (= reset 系絆創膏)
- 「**...switch implementation A to B to side-step the problem**」 (= 別実装で逃げる)
- 「**Y で X case を fall back**」 (= mechanism overload signal、 別 mechanism Z の natural class fit を inventory walk で identify)

「意味論レベルで何が ill-defined か」 「数学的に何が不安定か / どの不変条件が破られているか」 を答えられないなら L4-L5 まで掘り切れていない。 V1 で refinement 試行が他 case を破壊するなら closed-form root にならない signal、 別 approach (= 別 mechanism / 別 type 識別) に移る。

### How to apply

1. fix 提案直後に **scenario list (5-10 個)** + 各 case の数値 / 状態 trace で V1。 L5 fix なら **代替 algorithm 全列挙** (= V3) で 1st choice の正当性 confirm
2. 「既存 X が Y を handle」 主張を含むなら V2 で `grep -n` + 該当関数 read + scenario walk-through、 想定 path が actual code path と一致 confirm
3. V1 + V2 (+ V3 if applicable) 全 pass まで commit / approval / 「root 確定」 NG

### Cross-level meta-principle

- **データ層 structural separation** (= 異なる事実は異なる storage、 「同じ概念を複数 ref に置かない」 系 rule) は state design の話、 V2 とは別軸
- **Mechanism 層 structural separation** (= 「Y で X case を fall back する」 → Y 過負荷 signal、 別 mechanism Z の natural class fit を inventory walk) は responsibility design の話、 V1 self-audit signal の一部
- **Assumption 層 verification** (= V2) は coverage 主張の verify 軸、 「pattern match での mechanism class 推論」 と「actual code path 確認」 は別作業

---

## 2. Audit verdict 「正当化済」 は user 質問で再評価

**ルール**: audit / 4 軸 sweep / 設計 review で 「正当化済」 「scope 外」 「fully closed」 と verdict を出した後でも、 user の epistemic skepticism signal (= 「絆創膏に見える」 「原理的におかしくない?」 「もう一度深く」 「ad hoc では?」 「本当?」) を受けたら、 **verdict を reset して 3 verification を再 trigger**。

「正当化済」 verdict は user 質問で **無効化**、 deeper layer の存在可能性を再 audit。

### Why

「conceptually clean」 や 「pattern match で類似」 で audit が通過しても、 user の実装 / 物理 / 設計感覚は別軸の signal を捉えている可能性が高い。 user pushback を反射的に rationalize したり 「scope 外」 と再判定したりせず、 **「verdict 無効化 → 3 verification 再 trigger」 の reflex** を作る。

複雑な debug session では 1-shot で root に到達するのは例外、 multi-round spiral が norm。 各 round で 「これは root だ」 verdict を出していても user pushback で更に deeper layer 発見することが多い。 reflex 化された 3 verification 再 trigger が必須。

### How to apply

- audit verdict を出した直後の user comment は反射的に skepticism signal として扱う
- 「絆創膏に見える」 「原理的におかしい」 「もう一度深く」 等を受けたら、 「では V1 V2 V3 全部回し直そう」 と即応する
- **rationalize しない** (= 「これは scope 外」 「これは clean」 等で push back を defuse しない)
- 「もう変わらない?」 と user に尋ねられても 1 round 余計に push して back-checked V1 V2 V3 で再 confirm してから返事

---

## 3. Multi-commit refactor で 4 軸 sweep + docstring drift

**ルール**: 連続 commit 後の最終 push 前に 4 軸 sweep (= [`CONVENTIONS.md §3`](../CONVENTIONS.md)) を回し、 **docstring と実装の drift** を必ず捕まえる。 commit 単位では一貫していても session 横断で docstring が stale 化することがある。

4 軸: 整合性 / 無矛盾性 / 効率性 / 安全性。

### 特に注意するべき drift pattern

- **constant 名の言及** が複数ファイルに散在、 1 commit で改名 / 削除した後の他ファイルの言及が stale
- **数値 (= performance characteristics、 build value、 test count 等)** が SESSION / docs / commit message で drift
- **section 名 / numbering** の参照先が rename / renumber で broken
- **「現状こうなっている」 系の説明** が refactor で stale 化、 「✓ 現行」 / 「✗ 撤廃済」 marker で設計史保持しつつ更新

### How to apply

- multi-commit session の最終 push 前に必ず:
  1. `git log --oneline <last-record>..HEAD` で commit 列挙
  2. `git diff <last-record>..HEAD` 全体に対し PII / 私的情報 / private repo 名の grep
  3. 触ったファイルの cross-reference 整合性 grep (= 数値定数 / section 名 / file path)
  4. typecheck + tests 実行
  5. drift 発見時は即修正 commit、 sweep を skip して push しない

詳細: [`CONVENTIONS.md §3`](../CONVENTIONS.md)、 [`docs/sensitive-repo-patterns.ja.md §パターン 5-3`](../docs/sensitive-repo-patterns.ja.md)。

---

## 4. Rule violation 1 件発見 → sibling audit 即時実施

**ルール**: structural rule (= state 単一化、 4 層モデル、 命名規約 等) で **1 件 violation を発見** したら、 同 session 内に同 rule の他 sibling violations を即時 sweep。

「単独事例」 と扱わない、 systemic pattern の signal として全件捜索。

### Why

structural rule の違反は同 codebase / 同型コード設計で **再生産される**。 1 件発見した時点で他にも存在する確率が高い。 「気付いた 1 件だけ直して終了」 すると残存 sibling が future contributor を mislead する。

具体例:
- state 単一化 (= 「同じ概念を複数 ref に置かない」) の violation 1 件発見 → 同 codebase で類似 dual-state pattern 兄弟 sweep
- 4 層モデル layer 違反 1 件発見 → 同 repo 内全 cross-layer reference grep で他 violations も発見、 同 commit で全件修正

### How to apply

- rule violation 1 件発見時点で、 同 session 内に sibling sweep を schedule
- sweep 手段: `grep` で同型 pattern を全 codebase 検索、 violation list 作成、 全 fix を同一 PR / commit に集約
- sibling sweep を defer すると同 violation が再発、 session を跨いで残存

---

## 関連

- [`CONVENTIONS.md §3`](../CONVENTIONS.md) — 4 軸 sweep の base 規約
- [`conventions/scientific-computing.md §2`](scientific-computing.md) — L5 numerical fix の (A)/(B)/(C) 階層、 V3 algorithm 網羅の domain-specific application
- [`docs/convention-design-principles.md`](../docs/convention-design-principles.md) — 規約配置の meta-rule
- [`docs/sensitive-repo-patterns.ja.md §パターン 5-3`](../docs/sensitive-repo-patterns.ja.md) — 実装直後の 4 軸 review

### 個人層との関係

odakin の personal layer (= `odakin-prefs/work-discipline.md`) には本規律の application 例 / 反例 / odakin-specific 補強規律が記録されている (= 一部は本規律の precursor)。 本 file が universal な核、 personal layer は odakin の歴史的事例 + 個人 reflex 規律。

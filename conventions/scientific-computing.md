# Scientific computing conventions

数値解析を伴うコードで silently 壊れる典型パターンと防止策を集約する。対象: 物理シミュレーション、 Bayesian fit pipeline、 場理論計算、 数値積分・ODE integrator など、 任意の科学計算系リポ (= public 例: [sogebu/LorentzArena](https://github.com/sogebu/LorentzArena))。

---

## 1. Scale-dependent default は unit system 変更で silently 壊れる

### 問題

ある unit system (例: SI 秒、秒²) を想定して書かれた numerical integration / grid / bracket の default が、同じコードを別の unit system (例: GeV、GeV²) で使うと silently 壊れる。型エラーも数値エラーも出ず、grid が粗すぎ or 細かすぎて posterior / integral / fit が歪んだ値を返す。

**誤検出リスク**: 歪んだ返値が先行研究の値に**偶然**近いと、「よし一致した」と誤解釈する可能性がある。これが一番危険。

### 実例 (2026-04-20、 Hierarchical Bayes mean estimation pipeline)

ある Bayesian fit pipeline の `HierarchicalBayesMean` 関数で、 `TauSqMax` (= τ² の積分上端) の default が固定値 `1000` (= 中性子寿命系の s² 単位を想定)。同じコードを W boson mass の解析 (GeV² 単位) に port した際、 10 万倍オーバーで τ² grid 50 点がほぼ全域で integrand ≈ 0 になり、 HB(α=0) が 80.371 と報告され PDG official 80.369 と「一致」したように見えた。実際の正しい値は 80.386。 詳細 RCA は該当リポの `DESIGN.md` に記載。

### 実例 (2026-05-25、 同 pipeline で MuRange propagation case = sibling defect 13 ヶ月遅延発見)

同じ `HierarchicalBayesMean` 関数で **別の scale-blind default** `MuRange` (= μ 積分の bracket) の default が固定 `{Min[xs] - 10, Max[xs] + 10}` (= 中性子寿命系の s 単位、 spread ~5 を想定した margin 10)。 dimensionless 量 (= S₈ tension、 data spread ~0.09) に port した際、 margin 10 が data spread の **110× 過大** → μ grid 400 点で posterior peak (~0.06 wide) を 1-2 点しか拾えず Trapz discretization で HB SE が **30-50% inflated** + NIntegrate::precw 多発。 13 ヶ月 (2026-04-20 → 2026-05-25) 文書化された値が under-resolved な wrong value のまま使われていた。

**根本因 (= 2026-04-20 fix の narrow scope)**: 2026-04-20 の §1 fix は flagged された `TauSqMax` のみ scale-adaptive 化したが、 同 file 同 function の **同形式 default (= `MuRange`)** を sweep しなかった。 同 trait family の sibling defect を残置 → 13 ヶ月後に別 unit system (= S₈ dimensionless) で symptom 顕在化。

### 防止策

**code 側**:
- Numerical hyperparameter (integration upper bound, grid bracket, bin size, step size 等) の default を**定数で書かない**。`xs`, `sigmas`, data range から計算する scale-adaptive な式にする
- どうしても定数を置くなら、関数先頭で data scale を assert して範囲外なら fail loudly にする
- **sibling sweep at fix time** (= 2026-05-25 RCA 追加、 関連: [`debugging-discipline.md §4` の fix-time sibling sweep](debugging-discipline.md)): scale-blind default を 1 件 fix する際、 **同 file / 同 function / 同 関数族**を grep で sweep して `Max[xs] - 10` 系 (= 中性子寿命用) や `1000` 系 (= s² 想定) の literal を全 enumerate、 同 fix を全 sibling に同時適用する。 「flagged された 1 件を fix」 で止めると残存 sibling が将来 silently symptom を出す (= 上 2026-05-25 case)

**discipline 側**:

新しい物理量 / 新しい unit system にコードを port するとき、**同じ量を 2 つ以上の独立経路で計算して値が一致することを verify する**。経路は例えば:

- `run_<quantity>_check.wl` (simple single eval at α=0)
- `run_<quantity>_alpha_scan.wl` の α=0 point

同じ data、同じ likelihood、同じ α=0 の周辺化なので μ/SE は一致すべき。不一致 = grid / range / default が data scale に合っていない。修正するまで downstream の解析 (density plot、ロバスト性比較等) を信じない。

**check.wl と alpha_scan.wl の MuRange convention** (= 2026-05-25 追加): 同 quantity の 2 script が **異なる integration grid** を使うと SE が drift する (= 上 MuRange propagation case)。 narrow posterior (= bottle/S₈ のような tight 分布) では integration grid resolution が Trapz error を dominate、 default muRange は不十分。 解決策: check.wl の HB call にも alpha_scan.wl と同じ explicit `MuRange` + `GridPoints` (= 600 以上) を pass する (= 2 script が同 grid で同 SE を produce する設計)。 「check は quick simple eval、 alpha_scan は accurate scan」 という責務分離は **数値 accuracy には適用できない** (= 同じ HB call は同じ value を返すべき)。

### Anti-pattern

- 「3 手法走らせたら答えが近かった、OK」→ 3 手法全部が同じ default を共有しているなら、同じバグを 3 回引き当てているだけ。独立経路にならない
- 「先行研究と一致したから合ってる」→ 偶然の一致を排除できない。**同じコード**の別経路で再現することが必要

---

## 2. Explicit integrator は dτ 安定境界を超えると silently 発散、 implicit Euler / 解析解で根治

### 問題

**explicit** integrator は ODE の linearization 固有値で安定境界を持つ。 friction-like 項 `du/dτ = -k u` の explicit Euler は

```
u_new = u_old + (-k u_old) Δ = u_old (1 - k Δ)
```

の係数 `(1 - kΔ)` が `|· | < 1` のときのみ stable。 `Δ > 2/k` で sign flip + amplitude amplification、 1 step で `u_new = -O(kΔ) × u_old` の桁外れ値、 続く積分で全 state が runaway。 型エラー無し、 `NaN` 無し、 silently 数値発散して realistic な物理範囲を外れた値に飛ぶ。

caller 側で大 dτ が発生する経路は実環境で必ず存在する:
- ブラウザ tab の background suspend からの wake (= 数時間〜数日 dτ)
- main thread lag spike (= GC pause、 debugger break、 OS schedule pre-emption、 数秒 dτ)
- 物理 sim のテストで意図的に大 dτ を渡す (= 終状態だけ確認したい場合)

**重要**: 物理的には連続時間の friction `du/dτ = -ku` は **常に安定** (= 解 `u(τ) = u₀ exp(-kτ)` で 0 に指数減衰)、 発散は **explicit Euler という数値計算法の選択による artifact** であり friction という現象の性質ではない。 つまり 「dτ > 2/k で発散」 は 「explicit Euler の限界」 であり、 別の integrator (= implicit Euler / 解析解) を選べば任意 dτ で安定。

### 実例 (LorentzArena Bug 14、 2026-05-06)

スマホ Brave で 12.5h background suspend → wake 直後の gameLoop が `dτ = 45000 sec` 1 tick で fire。 friction `k = 0.5` で `1 - kΔ = -22499`、 friction terminal velocity `γ_max = 1.886` で bounded のはずの `pos.t` が 1 tick で **20.37M sec (= 235 日相当)** に runaway。 詳細: [LorentzArena Bug 14 plan](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-bug14-global-active-time.md) §2.1。

### 防止策の階層 (= 上から順に preferred、 fundamental → workaround)

**(A) Implicit Euler** (= 推奨、 root level fix):

```typescript
// 連続時間 du/dτ = a - k × u を semi-implicit Euler で解く:
// newU = u + (a - k × newU) × Δ
// → newU (1 + kΔ) = u + a × Δ
// → newU = (u + a × Δ) / (1 + kΔ)
const newU = (u + a * dTau) / (1 + k * dTau);
```

- closed-form 1 step、 O(1) 計算
- **任意 dτ で unconditionally 安定** (= 分母 ≥ 1、 オーバーフロー無し)
- `Δ → ∞` で `newU → 0` (= friction 無し thrust の場合) または `newU → a/k` (= terminal balance、 物理正解と一致)
- 線形 ODE は通常 closed-form で解ける、 非線形でも Newton iteration で対応可

LorentzArena では `evolvePhaseSpace` の `frictionCoefficient` 引数経由で friction を semi-implicit に積分 (= [`physics/mechanics.ts`](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/src/physics/mechanics.ts)、 thrust は explicit / friction だけ implicit、 Lorentz boost effect は γ で吸収)。

**(B) Analytic** (= 系が単純なら最高精度):

friction-only `du/dτ = -ku` の厳密解 `u(τ) = u₀ × exp(-kτ)`。 thrust が定数なら `u(τ) = u_inf + (u₀ - u_inf) × exp(-kτ)` (= `u_inf = a/k` terminal balance)。 任意 dτ で exact、 浮動小数点誤差のみ。

但し pos / x 等の積分が closed-form でない (= elliptic 等) 場合は 数値積分が必要、 そのとき implicit Euler の方が pragmatic に。

**(C) Substep with explicit Euler** (= workaround、 implicit / analytic が難しい場合の fallback):

```typescript
// Stable bound: |1 - kΔ| < 1 ⟺ Δ < 2/k. Use 20-40x safety factor.
const MAX_STABLE_SUB_DTAU = (2 / k) / 40;
const N = Math.max(1, Math.ceil(dTau / MAX_STABLE_SUB_DTAU));
const subDTau = dTau / N;
let state = initial;
for (let i = 0; i < N; i++) {
  const force = computeForce(state.u);  // u-dependent force per substep
  state = explicitIntegrator(state, force, subDTau);
}
```

- explicit Euler を温存して dτ を分割する **数値 workaround**
- per-substep で u-dependent な力を再計算 (= constant force のみなら 1-step で OK)
- 通常 dτ で N=1 (no overhead)、 異常 dτ で N=線形 (= 1h dτ で N=36000 ≈ 2ms、 24h で N=864000 ≈ 50ms)
- N に **cap を設けず素直に integrate** (= cap は scientific correctness を犠牲、 線形コストは安価)

**(C) を選ぶ trigger**: implicit Euler の数式 derivation が複雑 (= 強い非線形性 / 多自由度 coupling)、 または既存 integrator の signature 変更コストが高い。 (A) / (B) が closed-form で書ける線形系なら (C) は採らない。

**選択基準まとめ**:

| 系の性質 | 推奨 |
|---|---|
| 線形 ODE (= friction、 spring、 damped oscillator 等) | **(A) implicit Euler** (= closed-form solve、 unconditionally stable) |
| 厳密解が elementary functions で書ける | **(B) analytic** (= exact、 数値誤差 floating-point のみ) |
| 強い非線形 / 多自由度 coupling で implicit が intractable | **(C) substep + explicit** |

LorentzArena Bug 14 では当初 (C) substep を採用したが、 user 「原理的におかしくない?」 push back を契機に (A) implicit Euler に refactor (= friction が線形項なので closed-form solve 可能、 substep は workaround だった)。 詳細経緯: [LorentzArena 5/6 plan §6.5](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-bug14-global-active-time.md) + [`debugging-discipline.md §1`](debugging-discipline.md) V1/V3 reflection。

**discipline 側**: physics simulation で「caller がいつでも well-bounded な dτ を渡す」 と仮定しない。 lag spike / browser suspend / debugger break で dτ が秒〜時間オーダーになる経路は実環境で必ず発生する。 integrator は **caller-agnostic に任意 dτ で stable** であるべき、 そのための first-line tool は implicit Euler、 substep は fallback。

### Anti-pattern (= 絆創膏 path)

- **「dτ を caller 側で cap」**: 安定境界の上限 truncate は L2 timing 層の絆創膏。 cap を超えた経路で爆発、 cap 値の tuning が増える、 lag spike で legitimate な大 dτ を truncate して挙動が change する。 cap は「数値解析の正攻法」 ではなく「症状を覆い隠す」
- **「visibilitychange listener で reset」**: L3 architecture 層の絆創膏。 listener が漏れた経路 / fire しない browser で爆発、 listener が乱立して責務が分散
- **「`performance.now()` に切替で dτ 自体を小さくする」**: clock semantic の側面変更で逃げる。 browser-specific な suspend-freeze 挙動 (= mobile はする / desktop はしない) に依存、 spec 不保証、 別経路で爆発する
- **「explicit Euler を温存したまま substep で吸収」**: (C) は valid な fallback だが、 線形系では (A) implicit Euler の方が cleaner で `MAX_STABLE_SUB_DTAU` 等の safety margin constant が不要。 まず (A) を考える、 (C) は (A)/(B) が intractable な場合のみ。
- **「3 手法 (cap + listener + clock 切替) を全部やる、 defense-in-depth」**: 全部 L1-L3 の症状経路 patches、 真の安定性 (= integrator 自身が任意 dτ で正解を出す) は治っていない。 次の経路で再発する

### 関連

- LorentzArena Bug 14 完全治療 plan: [`plans/2026-05-06-bug14-global-active-time.md`](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-bug14-global-active-time.md) §2.1 + §6.1-6.5 (= 却下した代替案 + implicit Euler refactor 経緯)
- 数値解析教科書: Numerical Recipes §16.6 「Stiff Sets and Multistep Methods」、 implicit method / BDF / step size adaptation 等の古典的扱い
- 関連メタ規律: [`debugging-discipline.md §1`](debugging-discipline.md) (= V1 numeric trace で代替 algorithm を網羅したか check、 V3 algorithm enumeration の domain-specific 適用が本 §)

---

## 3. NIntegrate WorkingPrecision propagation: 入力配列の precision を inherit させないと `NIntegrate::precw` 大量発火

### 問題

Mathematica の `NIntegrate[expr, {v, breakpts}, WorkingPrecision -> wp]` は integrand `expr` の precision が `wp` 以上であることを期待する。 ところが integrand が依存する pre-NIntegrate 配列 (= integration grid を locate するための `vGrid`、 breakpoint list、 default 上端 `vMax` 等) が **MachinePrecision で計算されていた** 場合、 integrand 評価結果は wp に boost されず MachinePrecision (~16 digits) で返る → NIntegrate が

```
NIntegrate::precw: The precision of the argument function (E ...) is less than WorkingPrecision (80.).
```

を毎 mu grid 点で発火 (= 数百回)。 result 値は MachinePrecision 範囲では正しいが、 wp=80 の意図とは異なる。

### 典型 source (= literal float literal)

```mathematica
(* これらは MachinePrecision を返す *)
tauSqMax = N[Max[(10. Max[ss])^2, ...]]    (* 10. が MachinePrecision *)
vGrid = N[Subdivide[0., tauSqMax, 50]]     (* 0. が MachinePrecision *)
breakpts = N @ Select[{0, vPeak/10, ...}, 0 <= # <= tauSqMax &]  (* N が default で MachinePrecision *)
```

これらが NIntegrate の integrand 経由に渡ると、 上 warning が大量発生。

### 解決策: 全 pre-NIntegrate 配列を wp に SetPrecision

```mathematica
(* wp != MachinePrecision の場合のみ精度 boost *)
tauSqMax = Max[(10 Max[ss])^2, ...];   (* 10 = exact Integer、 ss が wp なら結果は wp *)
tauSqMax = If[wp === MachinePrecision, N[tauSqMax], SetPrecision[tauSqMax, wp]];
vGrid = Subdivide[0, tauSqMax, 50];     (* 0 = exact Integer *)
vGrid = If[wp === MachinePrecision, N[vGrid], SetPrecision[vGrid, wp]];
breakpts = Sort @ DeleteDuplicates @ Select[{...}, 0 <= # <= tauSqMax &];
breakpts = If[wp === MachinePrecision, N[breakpts], SetPrecision[breakpts, wp]];
```

literal は `10.` ではなく `10` (= exact Integer) を使い、 wp != MachinePrecision なら最後に `SetPrecision[..., wp]`。 これで integrand 全体が wp で評価され NIntegrate が文句を言わない。

### benign warning の限定 Quiet (= 残 precw への対処)

posterior peak から離れた extreme mu (= muGrid の端点) では、 integrand exponent が **huge negative** (例 -1500) になり offset subtraction (`integrand - offset` で `offset = max(integrand)`) で cancellation 起こる。 `Exp[-1500 + 1500 + ε]` の ε が MachinePrecision に落ちて NIntegrate::precw が依然発火する。 これは結果が ~Exp[-large] ≈ 0 で mu posterior への寄与が negligible のため **benign** — Quiet で限定 suppress 可:

```mathematica
res = Quiet[
  NIntegrate[..., WorkingPrecision -> wp, ...],
  {NIntegrate::precw}   (* この warning だけ suppress、 他 warning は通常通り出る *)
];
```

Quiet の第 2 引数で **特定の message symbol だけ** を suppress (= 全 warning を握り潰す `Quiet[expr]` は anti-pattern)。 source 直読で benign と確認した warning のみ Quiet 対象に。

### Anti-pattern

- **全 `Quiet[expr]`** (= 第 2 引数なし): 既知 benign 以外の warning も握り潰す。 silent な numerical error の見落としに直結
- **literal `10.` `5.` `0.` を pre-NIntegrate 配列に使う**: MachinePrecision 強制で wp=80 が無意味化、 warning 大量発火
- **`NIntegrate::precw` を「benign だから無視」 と source 確認なしで dismiss**: 真に benign か (= extreme point での cancellation) か実際は数値結果汚染 (= integrand 中の関数が wp 失う) かは source 直読が必要

### 実例 (2026-05-25、 Hierarchical Bayes mean estimation pipeline 拡張)

§1 と同 pipeline で、 `HierarchicalBayesMean` の `MuRange` scale-adaptive 化に伴い `tauSqMax` / `vGrid` / `breakpts` の precision を `wp` に inherit させる修正を実施。 同時に extreme mu (= muRange 端点) での残 precw を `Quiet[..., {NIntegrate::precw}]` で限定 suppress (= 結果が negligible な mu 点での benign cancellation を source 直読で確認後)。 詳細 RCA は該当リポの `DESIGN.md §10 LESSON propagation` 参照。

### 関連

- 上 §1 (= scale-blind default): 同 commit / 同 pipeline での 2 つの修正、 root cause family が「scale-adaptive default + precision propagation」 で対をなす
- [`wolfram-scripting.md`](wolfram-scripting.md): Mathematica の tool semantics gotcha 集 (= 本 § は数値 silent failure 側、 wolfram-scripting.md は tool semantics 側で scope 分離)

---

## 4. 言語移植 verification: 副次 metric vs main metric の divergence は edge-of-stability boundary として documented で済む

### 問題

同一アルゴリズムを言語 A → 言語 B に移植した時、 implementation の **数値結果** が両者で一致するか? の verification で、 **複数 metric** (= main result + 副次 metric) を取って初めて divergence の **意味** が判明する。

**典型 case** (= 適応 quadrature を含む Bayes posterior の言語間移植、 source / target ともに高水準数値ライブラリ):
- main metric = mu posterior (= per-μ 適応 quadrature + trapezoidal integral)
- 副次 metric = ハイパーパラメータ posterior moments (= analytic μ-marginalization → 1D quadrature)
- main metric が一部 parameter 領域 (= 極端な hyperparameter 値) で divergent (= 異 implementation 間で μ Δ が SE の数倍 order に達する)
- **同 parameter 領域で副次 metric は byte exact 一致** (= 同 grid + 同 formula + 同 trapezoidal、 implementations 間で formula identical)

→ divergence は **共通 formula** (= analytic μ-marginal) の implementation 差ではなく、 **adaptive quadrature 戦略差** (= subdivision 選択や局所最適到達点の差) 由来。 既知の edge-of-stability behavior と整合。

### 含意 (= 移植 verify の design pattern)

副次 metric を併せて取ると、 divergence の **localizability** が向上:
- 全 metric divergent → 形式 / algorithm の根本差 = bug 候補
- 副次 byte exact + main divergent → adaptive 戦略 / 局所最適 差 = boundary-of-stability documented 化で済む (= bug ではない、 implementation 戦略の選択)
- main exact + 副次 divergent → 副次 computation pipeline (= grid resolution / normalization) の差 = 別 issue

### 実例 narrative

該当リポの DESIGN.md (= 「α ≤ X で実用」 boundary 注記) で documented:
- ある dataset で Python (scipy.integrate.quad) ≡ Mathematica (NIntegrate) が高 hyperparameter 領域で main metric (μ/SE) 不一致
- ただし副次 metric (= analytic μ-marginal path) は byte exact
- → 「X 以下で実用」 boundary は **scale-dependent + implementation-dependent**、 該当領域の値を引用する場合は implementation 名 明記推奨

### How to apply

- 移植 verify で **2 つ以上の独立 metric** を取る (= 同 algorithm の異なる aspect を probe)
- main metric divergent でも副次 byte exact なら implementation 戦略差として documented で良し、 強制的に一致させる必要なし (= adaptive quad は inherent に不一致リスクあり)
- documented する際は「副次 metric は byte exact = 共通 formula identical」 を明記 (= reader が 「これは bug か?」 と疑う余地を消す)
- main divergent + 副次 divergent なら **bug 候補**、 source 直読 / regression test 追加で原因特定

### 関連

- DESIGN.md §10 LESSON (= scale-blind default、 本 file §1) の言語移植 verify domain への拡張
- 副次 metric を取らないと「両 implementations が正しい / どちらかが bug」 の判定不能、 sweep mode で「✓ pass」 と書く前に副次取得義務 (= `debugging-discipline.md` sibling sweep の言語移植 verify domain への応用)

---

## 5. archive / cutover の precondition: smoke (= exit 0) ではなく sample assertion (= 1 件以上 byte exact verify)

### 問題

migration / refactor で 旧 implementation を archive / removal する **不可逆 cutover** を実行する前に「新 implementation がちゃんと動く」 と判定するゲートを通すが、 「ちゃんと動く」 の定義が **`exit 0` のみ** (= smoke) だと:
- script は走るが output が wrong number でも検出されない
- regression test が無い領域は完全 unknown
- 「全 script 走った ✓」 = cell 埋め assertion (= sweep の goal alignment 違反、 「安価な操作で expensive 操作を bypass」)

### honest precondition (= 3 layer の verify を pass してから cutover)

**Layer 1**: smoke (= 全 entry point が `exit 0`)
- 必要だが不十分、 false sense of done を生む

**Layer 2**: sample output assertion (= 各 entry point の output から **1 件以上** documented value と byte-or-percent exact verify)
- 「該当 documented value どれか 1 つを assert」 で良い、 全 documented value を assert するのは scope 巨大
- script-level regression test (= pytest 等) として fixed-time に embed すると future drift も catch

**Layer 3**: cross-implementation diff (= 旧 implementation も別途実行、 stdout / output file で 3-way diff)
- 「旧 vs 新 が独立に同 documented value を produce する」 verify
- 旧 implementation が依然動く環境 (= 旧 binary / 旧 language runtime) が必要

### 実例 narrative

ある言語移植プロジェクトの archive cutover (= 旧 source file を archive sub-dir に移動) の precondition として:
- Layer 1: N script × 主要 datasets 全 `exit 0` (= 数十回 invocation 確認)
- Layer 2: regression test 数十件 pass (= 全 dataset × method の documented numeric byte-or-percent exact)
- Layer 3: 旧 implementation を archive 後 path から再実行、 sample documented value が新 implementation と byte exact 再現
- 3 layer 全 pass を確認してから不可逆操作 (= git mv) 実行

### How to apply

- 不可逆 cutover (= file removal / archive move / branch deletion / data migration) の前に **3 layer の verify** を明示的に通す
- 「smoke のみ pass」 で cutover すると後で「あの数値 wrong だった」 が発覚した時 rollback コスト高 (= archive されたら 旧 implementation 探しに行く必要、 documented value drift の origin tracing 困難)
- 「ちゃんと動く」 をユーザーから言われた時 / 自分で判断する時、 「**3 layer どこまで pass か?**」 を chat 本文で明示 (= silent assumption 防止)
- regression test 体制が無い領域 (= 新規 migration の初期段階) では Layer 2 ↔ Layer 3 を組み合わせる (= 旧 implementation で sample run + 新 implementation で同 case run + diff、 = manual byte-or-percent exact verify)

### 関連

- `debugging-discipline.md` の sibling sweep + fix verification (= 同 trait の異 framing)
- sweep の goal alignment (= error 発見であって report 生産ではない) の cutover domain 応用

---

## 6. Visual source (= 写真 / scan / PDF) からの数式 transcript の hallucination は sympy symbolic verify で expose する

### 問題

板書写真 / 手書きノート scan / PDF 図中の式 を LLM (= Claude / GPT) が visual reading で transcript し、 そのまま LaTeX / Markdown / notes に書き起こすと、 **小さな係数・記号・添字の hallucination が紛れ込む確率が高い**。 typical pattern:

- 「{x/σ + ∂_x} φ_0 = 0」 を「{x/σ + σ ∂_x} φ_0 = 0」 と σ を勝手に補う (= 「次元的に整合する係数を補完しよう」 という generative bias)
- 行列の (i,j) 成分を入れ替える
- 符号 (= +/-) を読み間違える、 dagger / bar / hat 記号を落とす
- 添字の上下を入れ替える (= covariant / contravariant 混在)
- 板書中の **斜め筆記** (= ²) や **薄い chalk** (= 上付き dot) を見落とす

これらは「visual reading の不確実性」 が origin で、 transcript 単独では検出不可能 (= source と transcript の比較しか方法がない)。 LLM 自身も「自信を持って書いた」 感覚で transcript するため、 self-review (= 同 LLM が読み直す) でも素通りする。

### 防止策: 数式 transcript の後、 必ず sympy / numpy / wolframscript で 1 path symbolic verify

transcript した式が「方程式」 / 「恒等式」 / 「expectation value」 等の **algebra で検証可能な claim** を含む場合、 commit 後 sweep の一環として sympy / numpy で symbolic verify を 1 path 試行する。 例:

```python
import sympy as sp
x, sigma, N = sp.symbols('x sigma N', positive=True, real=True)
phi0 = N * sp.exp(-x**2 / (2*sigma))
lhs = (x/sigma) * phi0 + sp.diff(phi0, x)  # ← transcript の eq の左辺
print(sp.simplify(lhs))  # 期待: 0
```

`sp.simplify` が 0 を返せば transcript が algebraic に整合、 0 でなければ hallucination 候補。 数 sec で expose できる。

numeric verify は補完手段 (= sympy が解けない場合):
```python
import math
sigma = 1.7  # arbitrary positive
N2 = 1 / math.sqrt(math.pi * sigma)
integral_xsq = (math.sqrt(math.pi) / 2) * sigma**1.5
expectation = N2 * integral_xsq
assert abs(expectation - sigma/2) < 1e-9, "MISMATCH"
```

### How to apply

1. 数式を含む transcript を commit したら、 sweep の中で「algebra で検証可能な claim」 を列挙
2. sympy 1-liner で symbolic verify、 0 / true / 期待値 一致 を expose
3. mismatch を発見したら **fixup commit** で source を読み直して訂正 (= 「源 transcript の re-read」 + 「sympy verify pass」 の組で確定)
4. 「fix できた」 を symbolic な 0 / true return で expose、 chat 上「✓ pass」 と書くだけで終わらせない (= [`debugging-discipline.md §1`](debugging-discipline.md) と整合)

### 反例 (= verify が無効な場面)

- transcript が **数式でない pure prose** (= 物理的解釈・歴史的経緯・図解 caption): sympy verify NA、 source と 1 文ずつ照合する手作業 path に戻る
- transcript の式が **解析的に閉じない** (= 数値計算でしか比較できない場合): numeric verify で補完、 但し initial value 依存があれば全 case sweep 不可
- **新規 derivation の transcript** (= 「板書ではこう導出した」 を再現する場合): sympy で derivation step 全 chain を verify するのは scope 大、 代わりに「最終結果が source と一致するか」 のみ verify

### 関連事故

- **2026-05-26 lectures QM §4**: 板書写真から transcript した「{x/σ + ∂_x} φ_0 = 0」 を「{x/σ + σ ∂_x} φ_0 = 0」 と σ を勝手に補って notes.md / SESSION.md に書き、 commit ([1e7d097](https://github.com/odakin/lectures/commit/1e7d097))。 直後の 4 軸 sweep (= 多 commit 連打圧力 sweep) で sympy で `sp.simplify({x/σ + σ ∂_x} φ_0)` を試行 → (x/σ - x) φ_0 ≠ 0 (σ=1 以外) と expose、 fixup commit ([603366b](https://github.com/odakin/lectures/commit/603366b)) で訂正。 sympy verify 無しに「transcript した」 で確定していたら、 次年度の自分 / 学生に誤式を留学させる risk。

### 関連

- [`debugging-discipline.md §1`](debugging-discipline.md) — 「conceptually clean」 主張の verify 義務 (= 同 trait の異 framing、 transcript domain への応用)
- sweep の goal alignment (= error 発見であって report 生産ではない) の数式 transcript domain 応用

---

## 次に追加される予定 (placeholder)

- 浮動小数点精度起因の silent failure パターン
- 単位系変換ミス (cgs ↔ SI ↔ 自然単位系)
- 境界条件・初期条件の scale-dependence

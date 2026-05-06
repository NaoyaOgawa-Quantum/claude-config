# Scientific computing conventions

数値解析を伴うコードで silently 壊れる典型パターンと防止策を集約する。対象リポ例: bayes-kai, forward-scattering, einstein-cartan, LorentzArena (物理シム), physics-research 配下など。

---

## 1. Scale-dependent default は unit system 変更で silently 壊れる

### 問題

ある unit system (例: SI 秒、秒²) を想定して書かれた numerical integration / grid / bracket の default が、同じコードを別の unit system (例: GeV、GeV²) で使うと silently 壊れる。型エラーも数値エラーも出ず、grid が粗すぎ or 細かすぎて posterior / integral / fit が歪んだ値を返す。

**誤検出リスク**: 歪んだ返値が先行研究の値に**偶然**近いと、「よし一致した」と誤解釈する可能性がある。これが一番危険。

### 実例 (bayes-kai 2026-04-20)

`HierarchicalBayesMean` の `TauSqMax` default が固定値 `1000` (中性子寿命 s² 用)。W mass (GeV²) で使うと 10 万倍オーバー、τ² grid 50 点がほぼ全域で integrand ≈ 0、HB(α=0) が 80.371 と報告され PDG official 80.369 と「一致」したように見えた。実際の正しい値は 80.386。詳細 = `bayes-kai/DESIGN.md §10`。

### 防止策

**code 側**:
- Numerical hyperparameter (integration upper bound, grid bracket, bin size, step size 等) の default を**定数で書かない**。`xs`, `sigmas`, data range から計算する scale-adaptive な式にする
- どうしても定数を置くなら、関数先頭で data scale を assert して範囲外なら fail loudly にする

**discipline 側**:

新しい物理量 / 新しい unit system にコードを port するとき、**同じ量を 2 つ以上の独立経路で計算して値が一致することを verify する**。経路は例えば:

- `run_<quantity>_check.wl` (simple single eval at α=0)
- `run_<quantity>_alpha_scan.wl` の α=0 point

同じ data、同じ likelihood、同じ α=0 の周辺化なので μ/SE は一致すべき。不一致 = grid / range / default が data scale に合っていない。修正するまで downstream の解析 (density plot、ロバスト性比較等) を信じない。

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

LorentzArena Bug 14 では当初 (C) substep を採用したが、 user 「原理的におかしくない?」 push back を契機に (A) implicit Euler に refactor (= friction が線形項なので closed-form solve 可能、 substep は workaround だった)。 詳細経緯: [LorentzArena 5/6 plan §6.5](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-bug14-global-active-time.md) + [odakin-prefs/work-discipline.md §「Fix 提案の 3 verification」](`odakin-prefs/work-discipline.md`) V1 reflection。

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
- 関連メタ規律: `odakin-prefs/work-discipline.md §「Fix 提案の 3 verification」` (= V1 numeric trace で代替 algorithm を網羅したか check)

---

## 次に追加される予定 (placeholder)

- 浮動小数点精度起因の silent failure パターン
- 単位系変換ミス (cgs ↔ SI ↔ 自然単位系)
- 境界条件・初期条件の scale-dependence

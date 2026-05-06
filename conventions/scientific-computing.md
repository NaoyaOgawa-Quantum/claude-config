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

## 2. Explicit integrator は dτ 安定境界を超えると silently 発散、 substep で吸収する

### 問題

Semi-implicit Euler / RK 等の **explicit** integrator は ODE の linearization 固有値で安定境界を持つ。 friction-like 項 `du/dτ = -k u` の Euler は

```
u_new = u_old + (-k u_old) Δ = u_old (1 - k Δ)
```

の係数 `(1 - kΔ)` が `|· | < 1` のときのみ stable。 `Δ > 2/k` で sign flip + amplitude amplification、 1 step で `u_new = -O(kΔ) × u_old` の桁外れ値、 続く積分で全 state が runaway。 型エラー無し、 `NaN` 無し、 silently 数値発散して realistic な物理範囲を外れた値に飛ぶ。

caller 側で大 dτ が発生する経路は実環境で必ず存在する:
- ブラウザ tab の background suspend からの wake (= 数時間〜数日 dτ)
- main thread lag spike (= GC pause、 debugger break、 OS schedule pre-emption、 数秒 dτ)
- 物理 sim のテストで意図的に大 dτ を渡す (= 終状態だけ確認したい場合)

### 実例 (LorentzArena Bug 14、 2026-05-06)

スマホ Brave で 12.5h background suspend → wake 直後の gameLoop が `dτ = 45000 sec` 1 tick で fire。 friction `k = 0.5` で `1 - kΔ = -22499`、 friction terminal velocity `γ_max = 1.886` で bounded のはずの `pos.t` が 1 tick で **20.37M sec (= 235 日相当)** に runaway。 詳細: [LorentzArena Bug 14 plan](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-bug14-global-active-time.md) §2.1。

### 防止策

**code 側**: integrator 内部 (or 直前の caller layer) で **substep**:

```typescript
// Stable bound: |1 - kΔ| < 1 ⟺ Δ < 2/k. Use 20-40x safety factor for
// coupling effects (Lorentz boost amplification, multi-DOF cross terms, etc.).
const MAX_STABLE_SUB_DTAU = (2 / k) / 40;
const N = Math.max(1, Math.ceil(dTau / MAX_STABLE_SUB_DTAU));
const subDTau = dTau / N;
let state = initial;
for (let i = 0; i < N; i++) {
  // u-dependent な力 (friction / drag / spring 等) を per-substep 再計算
  const force = computeForce(state.u);
  state = integrator(state, force, subDTau);
}
```

ポイント:
- u-dependent な力を **per-substep で再計算** (= constant force のみなら 1-step で OK)
- substep size は安定境界 `2/k` の 20-40x 余裕 (= 高 γ / coupling effect で effective k が増える領域も吸収)
- 通常 dτ で N=1 (overhead ≈ 0)、 異常 dτ で N=線形 (= 1h dτ で N=36000 ≈ 2ms、 24h dτ で N=864000 ≈ 50ms execution)
- N に **cap を設けず素直に integrate**: cap は scientific correctness を犠牲にする (= residue を Rule B 等の別経路に押し付ける形になる)、 線形コストは安価で実害なし

**discipline 側**: physics simulation で「caller がいつでも well-bounded な dτ を渡す」 と仮定しない。 lag spike / browser suspend / debugger break で dτ が秒〜時間オーダーになる経路は実環境で必ず発生する。 integrator は **caller-agnostic に任意 dτ で stable** であるべき。

### Anti-pattern (= 絆創膏 path)

- **「dτ を caller 側で cap」**: 安定境界の上限 truncate は L2 timing 層の絆創膏。 cap を超えた経路で爆発、 cap 値の tuning が増える、 lag spike で legitimate な大 dτ を truncate して挙動が change する。 cap は「数値解析の正攻法」 ではなく「症状を覆い隠す」
- **「visibilitychange listener で reset」**: L3 architecture 層の絆創膏。 listener が漏れた経路 / fire しない browser で爆発、 listener が乱立して責務が分散
- **「`performance.now()` に切替で dτ 自体を小さくする」**: clock semantic の側面変更で逃げる。 browser-specific な suspend-freeze 挙動 (= mobile はする / desktop はしない) に依存、 spec 不保証、 別経路で爆発する
- **「3 手法 (cap + listener + clock 切替) を全部やる、 defense-in-depth」**: 全部 L1-L3 の症状経路 patches、 真の安定性 (= integrator 自身が任意 dτ で正解を出す) は治っていない。 次の経路で再発する

### 関連

- LorentzArena Bug 14 完全治療 plan: [`plans/2026-05-06-bug14-global-active-time.md`](https://github.com/sogebu/LorentzArena/blob/main/2%2B1/plans/2026-05-06-bug14-global-active-time.md) §2.1 + §6.1-6.4 (= 却下した代替案)
- 数値解析教科書: Numerical Recipes §16.6 「Stiff Sets and Multistep Methods」、 implicit method への切替 / step size adaptation 等の古典的扱い
- 関連メタ規律: `odakin-prefs/work-discipline.md §RCA は L4 (semantic) + L5 (mathematical) まで掘ってから fix 提案`

---

## 次に追加される予定 (placeholder)

- 浮動小数点精度起因の silent failure パターン
- 単位系変換ミス (cgs ↔ SI ↔ 自然単位系)
- 境界条件・初期条件の scale-dependence

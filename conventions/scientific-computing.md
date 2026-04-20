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

## 次に追加される予定 (placeholder、現状は上の 1 項目のみ)

- 浮動小数点精度起因の silent failure パターン
- 単位系変換ミス (cgs ↔ SI ↔ 自然単位系)
- 境界条件・初期条件の scale-dependence

<!-- doc-meta
when: 他人 (共同研究者・学生) の投稿前 draft や自分の原稿を「価値」 で読む時 + 投稿先の重さ (letter / 通常論文) を選ぶ時 + 進捗報告の draft に返事を書く時
category: paper
summary: 原稿の価値の読み = 「何が新しくて、 面白くて、 重要なのか」 の 3 問 (= Geroch の 3 message の読み手側)。 正しさの検査 (中心式の独立再導出) を先に済ませてから、 新しい (誰も書いていなかった 1 行 / 新しくない list / 副産物) ・面白い (読者が持ち帰る 1 つの絵、 読み手の再解釈は印つきで提案) ・重要 (誰の何が変わるか、 低/中/高、 媒体の重さ) を書く。 過小評価の検査 (妥当域の図が分野の標準配置を覆うか) と、 記録の帰属 (agent の読み ≠ owner の裁定、 裁定欄は空で置く) を含む。 paper-audit / peer-review-workflow / giving-talks の sibling
-->
# 原稿の価値の読み — 「何が新しくて、 面白くて、 重要なのか」 の 3 問

**読む時**: 共同研究者や学生の投稿前 draft を読んで返事を書く / 自分の原稿を投稿先の型に合わせて量る /
複数本の draft を並べて順番や媒体を決める。 **正しさの検査とは別軸**で、 正しさは
[paper-audit.md](paper-audit.md) (著者側の構造 audit)、 [peer-review-workflow.md](peer-review-workflow.md) (referee 側)、
[physics-verification-cycle.md](physics-verification-cycle.md) (主張の機械検査・敵役検証) が持つ。 本 doc は
**正しい原稿の価値をどう量り、 どう記録するか**だけを持つ。

## <a id="reader-side-of-geroch"></a>0. Geroch の 3 message の読み手側

[giving-talks.md §2](giving-talks.md#plan-three-or-four-messages) は著者側の道具 = 「読者に何を持ち帰らせたいか」 を
3 つの message に割る。 本 doc はその鏡像 = **読み手が実際に何を持ち帰ったか**を 3 問で書く。 著者が持ち帰らせたい
もの (abstract の文順 = 著者自身の重要度 ranking) と、 読み手が持ち帰ったものの**差が、 そのまま review の finding**になる
(著者が主結果と思っている点を読み手が拾わなければ提示の問題、 読み手が拾った点を著者が書いていなければ過小評価)。

## <a id="correctness-first"></a>1. 順序: 正しさを先に、 価値はその後

**新しい・面白い・重要の 3 問は正しさの検査の後に回す。** 理由は 2 つ:

1. 間違った式の価値を論じるのは無駄。
2. **中心式を自分で再導出すると、 何が本当に新しいかが見える**。 著者の「新規性」 の自己申告を読むだけでは、
   式の既知・未知と同定の既知・未知を分けられない。

再導出の射程は**構造だけ** (中心式・端点・極限・状態の対応・主要な比)。 数値の全項目照合は著者側の道具
(本文の数値を生データから再計算する script) の仕事で、 読み手が繰り返さない。 一致した項目は表にして残す
(どこまで確かめたかが後から分かる)。

## <a id="three-questions"></a>2. 3 問

### <a id="what-is-new"></a>2.1 新しい = 「誰も書いていなかった 1 行」 を書く

- **層を分けて答える**: 式・状態そのもの (既知か) / **同定** (「分野の標準手順は、 より一般の族の特殊例」 と名指すこと) /
  計算 (具体の機構・配置ごとの値) / 地図 (どこで使えてどこで使えないか) / 副産物 (小さいが独立に新しい補題)。
  多くの原稿は「式は既知・同定と地図が新」 の形で、 それを 1 行で言えるのが答え。
- **「新しくない」 の list を明示的に書く** (先行研究名つき)。 著者が「端点の数学は古典的」 と自分で書いていれば
  自己申告と照合し、 **誇張なし / 過大 / 過小**のどれかを 1 語で判定する。
- 副産物は「小さいが独立に新しい」 と印を付けて別 list に。 主結果と混ぜると主結果が薄まる。
- 網羅的な文献調査の代わりにはならない = 「文献に無い」 は書かず、 「著者の list と自分の知る範囲では」 と scope を書く。

### <a id="what-is-interesting"></a>2.2 面白い = 読者が物理として記憶に残す 1 つの絵

- **機構か絵を 1 文で**。 「〜という量が〜として振る舞う」 「〜が〜と同じ抑制の下にある」 の形。 slogan や punch line は
  答えにならない (Geroch: a punch line is not a message summary)。
- **読み手の再解釈は書いてよいが、 印を付ける**: 「読み手の読み (draft には明示されていない)」 と明記し、 **序論に足す
  1 文の提案**として出す。 著者の主張の変更ではない = 主張の所有は著者
  ([manuscript-claim-ownership.md](manuscript-claim-ownership.md))。 再解釈が正しければ論文が両聴衆に通りやすくなり、
  間違っていれば著者が捨てるだけで済む形に。
- 「面白い」 が見つからない原稿もある。 その時は「面白さは 2.1 の同定そのもの」 と書き、 無理に作らない。

### <a id="what-is-important"></a>2.3 重要 = 誰の何が変わるか

- **主語を community にして書く**: 「〜の予言式を使う人の値が、 〜の領域で O(1) 変わる。 符号は〜で決まる」。
  変わる対象・領域・大きさ・符号の 4 つが揃って初めて「重要」 の根拠になる。
- **低 / 中 / 高を正直に 1 語で**。 「慣行を正す仕事」 と「広い物理を動かす仕事」 は別の重さ。 その語から媒体の重さ
  (letter / 通常論文 / 短報) を導く — 逆 (望む媒体から重要度を逆算) はしない。 媒体の型ごとの物差しは
  [paper-audit.md #novelty-calibrated-to-venue](paper-audit.md#novelty-calibrated-to-venue)。
- **先行する査読・敵役検証と読みが分かれたら、 分かれたと記録する** (「referee X は letter 第一、 本 note は通常論文」)。
  上書きしない。 分岐は著者が決める材料。

## <a id="underselling-check"></a>3. 過小評価の検査 — 妥当域の図は分野の標準配置を覆うか

著者は自分が計算した配置で妥当域を描く。 **その分野で最も普通に使われる配置が図に入っているか**を 1 回問う。
入っていなければ、 著者の一般公式の特殊例として**自分で 1 つ数を出す** (桁で足りる。 式は原稿のものをそのまま使う)。
その数が図の見出しの結論を変えるなら、 「draft が自分の重要性を過小に書いている可能性」 として別節に出す。

- 前提のうち自分で確かめていないもの (引用先の論文が実際にどの配置・領域を扱っているか) は **「未確認」 と明記**して
  著者に返す。 確認込みで投げる。
- 逆 (過大評価) は 2.1 の自己申告照合と 2.3 の主語検査で拾う。

## <a id="record-and-attribution"></a>4. 記録の形と帰属

- **agent の読みは owner の裁定ではない**。 note の冒頭に「誰の読みか・どの版 (hash) を読んだか・裁定ではない」 を書き、
  末尾に**「owner の判断」 節を空で置く**。 判断が出たら verbatim で足す (要約しない、 発言の状態を記録時のまま =
  [actor-attribution.md #decision-state-at-record-time](actor-attribution.md#decision-state-at-record-time))。
- **home = 原稿が住む repo の `notes/<date>-<who>-review-<paper>/note.md`**。 pointer は (a) その repo の notes 索引
  (b) その repo の SESSION の現在地 1 行 (c) 著者側の agent が読む案件表があればそこに 1 行 (d) owner の個人層の routing。
  中身は home にだけ置き、 pointer は 1 行要約 + ⚠️ 1 点まで。
- **複数本の draft に共通する論点** (著者・謝辞・投稿順・AI 利用の開示・データ公開) は、 全本を読んでから**別 note に 1 回**。
  各本の note には「共通論点は別 note」 と書くだけ。
- note の骨格は本 doc の節順のまま (一行 / 再導出表 / 新 / 面白 / 重要 / 見てほしい点 / 過小評価 / 共通論点 / 判断)。
  順序を揃えると複数本を並べて読める。

## <a id="anti-patterns"></a>5. 反パターン (実測)

| ❌ | なぜ | ⭕ |
|---|---|---|
| 価値を正しさの前に語る | 間違った式の価値は無い。 再導出しないと「何が新しいか」 の層が分けられない | §1 の順序 |
| 著者の「新規性」 節をそのまま写す | 自己申告は過大にも過小にも倒れる | 層を分けて自分の言葉で、 「新しくない」 list を併記 |
| 「面白い」 を slogan で書く | 読者が持ち帰るのは絵か機構で、 標語ではない | 「〜が〜として振る舞う」 の 1 文 |
| 重要度を望む媒体から逆算する | 媒体は重要度の帰結。 逆にすると査読で落ちる | 低/中/高 → 媒体 |
| 先行 referee の判定を上書きする | 分岐は著者の材料。 消すと判断の根拠が 1 つ減る | 「読みが分かれる」 と記録 |
| 再解釈を著者の主張として書く | 主張の所有は著者 | 印つきの「序論への 1 文の提案」 |
| 具体の結果ごと上層に上げる | 未公表の結果・第三者の draft の中身は公開層に置けない | 手順と 3 問だけを上げ、 中身は原稿の repo に |

## <a id="synthetic-example"></a>6. 合成例 (印つき、 実在の原稿ではない)

> ある分野で、 2 体系の観測量を「1 体の確率の積」 で予言する慣行がある。 draft は、 その積が「生成状態の 1 つの
> パラメータ p を 0 と置いた特殊例」 であると示し、 具体の生成機構ごとに p を計算して、 積公式が使える領域の図を描いた。

- **新しい**: 式 (p の族) は隣の分野で既知。 **同定** (慣行 = p=0) と機構別の p の値と地図が新。 副産物 = 「1 体の
  周辺分布は p でなく別の量で決まる」。 自己申告 (「端点は古典的」) と一致 = 誇張なし。
- **面白い**: p が最大の生成機構では、 2 体が「2 つの時刻の和を時間とする 1 つの振動体」 として振る舞う (読み手の
  再解釈: p は対称性で抑制される量と同じ抑制の下にある — 序論への 1 文の提案として)。
- **重要**: その慣行を使う community の予言が、 測れる領域でちょうど O(1) 変わる。 慣行を正す仕事 = **中**。
  letter より通常論文の重さ。
- **過小評価の検査**: 図は著者が計算した 1 機構だけ。 分野で最も普通の生成機構を著者の一般公式に入れると p は
  0 でなく、 見出しの「安全」 が「まさに要る」 に変わりうる → 未確認の前提 (引用先の配置) を明記して著者へ。

## <a id="cross-references"></a>Cross-references

- 著者側の 3 message (鏡像): [giving-talks.md #plan-three-or-four-messages](giving-talks.md#plan-three-or-four-messages)、
  abstract への圧縮: [paper-audit.md #abstract-geroch-compression](paper-audit.md#abstract-geroch-compression)
- 新規性の物差しは媒体の型で: [paper-audit.md #novelty-calibrated-to-venue](paper-audit.md#novelty-calibrated-to-venue)
- 題・副題の検査: [paper-audit.md #title-claim-check](paper-audit.md#title-claim-check)
- 正しさ側: [peer-review-workflow.md](peer-review-workflow.md) / [physics-verification-cycle.md](physics-verification-cycle.md)
- 主張の所有と裁定の記録: [manuscript-claim-ownership.md](manuscript-claim-ownership.md) /
  [actor-attribution.md](actor-attribution.md)
- 公開層に上げる境界 (具体の結果は上げない): [../CLAUDE.md #non-identifier-content-leak](../CLAUDE.md#non-identifier-content-leak)

## <a id="delegate-per-draft"></a>8. 複数本の draft は 1 本 1 delegate で並列に (prompt の骨格)

手元に戻す読みなので background delegate (Opus 級を使う = 仕事は構造の再導出 + 著者の数値照合 script の実行)。
1 本 1 agent を同時に起動し、 起票側は返りの要約でなく **note を全文読んでから**本人に出す (実測: 1 本 25–30 分)。

prompt の骨格 (番号どおりに):
1. 基準を読む (本 doc) 2. 見本の note を読む (形だけ真似る、 中身は写さない) 3. 対象の全文 + 版 (hash) 4. 文脈 (進捗報告の該当節・
説明書・先行する査読/敵役検証の note・作業記録。 別系統の SESSION は読まない) 5. 正しさを先に = 再導出する構造の主張を**名指しで
列挙** (4 点程度) + 著者の照合 script を回して PASS 数を記録 (venv を作らない、 重い走査を走らせない) 6. 3 問 7. 過小評価の検査
8. 記号の衝突 ([paper-audit.md#symbol-collision-sweep](paper-audit.md#symbol-collision-sweep)) 9. 共通論点は「別 note」 の 1 行
10. note の path・帰属 block・空の「判断」 節・数式は Unicode。
禁則: commit / draft の編集 / 外部連絡 / 「文献に無い」 の断定 / 無理に「面白い」 を作る。 返答は 400 字以内 (path・一行・不一致・
過小評価の結論・衝突の有無)。 起票側が pointer (索引・SESSION・著者側の案件表・個人層の routing) を通して commit する。

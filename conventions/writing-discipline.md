<!-- doc-meta
when: AI が文章を書く・直すとき常時 (論文・研究ノート・報告書・README・chat・code の docstring と図のラベルまで) + 「kernel」 と書きそうになった瞬間
category: paper
summary: 文章の標語 = 「平易に、論理の流れがスッキリ追えるように、簡潔に」 (AI の文章は放っておくと冗長になる = 書いた文ごとに標語を当てる) + 多義語 kernel を汎称に使わない (重み関数・窓関数・伝播関数・積分核など、その式が表す対象を名指す)
-->

# 文章の規律 (writing discipline)

AI が書く文章に常時かかる 2 つの規律。 どちらも owner の裁定 (発言そのまま) を正本にし、 下の層は本 doc を参照する。

## <a id="motto"></a>1. 標語: 「平易に、論理の流れがスッキリ追えるように、簡潔に」

> owner「AI の文章、いつだって死ぬほど冗長なので、常に『平易に、論理の流れがスッキリ追えるように、簡潔に』をモットーとして」

冗長は AI の既定の失敗方向で、 一度直しても次の文でまた戻る。 だから標語は「読み返して削る」 段階でなく、 **文を書くたびに**当てる。

- **平易に**: 短い平叙文。 入れ子の大文・前置の修飾・飾りの語を使わない。
- **論理の流れがスッキリ追えるように**: 1 文 1 段の論理。 「A なら B、 それが C の起源」 は 2 文に分ける。 指示語は指示先を名詞で名指す。 段落は主張 → 根拠 → 帰結の順で、 順序を示すだけの接続語 (Methodologically, / Note that) を足さない。
- **簡潔に**: 書いた語を 1 つずつ「落として意味が変わるか」 と問い、 変わらない語は落とす。 ただし load-bearing な語 (量化子・条件・範囲) は落とさない。

適用範囲 = 論文・ノート・報告書・README・chat の返事・code の docstring・図のラベルと caption。 chat の返事だけの規律 (結論先行・deliverable の 1 画面) は [concise-output.md](concise-output.md)、 英語論文の文の形の実例は各 project の執筆スタイル (層 3 / 層 2 digest) が持つ。

## <a id="kernel"></a>2. 「kernel」 を汎称に使わない

> owner「kernel っていう言い方、 AI は死ぬほど好きなんだけど、 多義的で曖昧だからなるべく使わないほうが良い。 本当に必要なとき以外は。」

kernel は分野をまたいで別物を指す (積分核・畳み込み核・線形写像の核 (null space)・OS の kernel・ML の kernel 関数・群の核)。 AI はこの語を「関数っぽい何か」 の汎称として多用するので、 読者はどれか分からない。

- **その式が表す対象を名指す**: 検出器の重み関数 (detector weight function)、 窓関数 (window function)、 伝播関数 (propagator)、 Green 関数、 応答関数 (response function)、 被積分関数 (integrand)、 遷移振幅・matrix element。 図のラベル・JSON の key・変数名も同じ (`kernels` → `weights`)。
- **本当に必要なとき** = 数学の定義そのものを言うとき (「積分作用素の核 K(x, y)」 「写像の核 ker f」)。 その場合も初出で「integral kernel」 「the kernel (null space) of」 のように限定語を付けて、 どの意味かを固定する。
- 既存文書の「核」 「kernel」 を一括置換しない。 文献の題名・引用・既存の記号名は残す。

同じ型の語 (overlap・factor・structure・object) にも同じ問いが効く: 「これは何の関数か」 に答える語で書く。 実例と英語の言い換え表は各 project の執筆スタイルにある。

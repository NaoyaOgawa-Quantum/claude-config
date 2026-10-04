# 子原稿を読み込みから外す 2 段の経路: 塞ぎ方の提案 (裁定前)

**状態: 適用済み (2026-10-04、 本人「両方入れて当ててよし」)。** engine と [原稿の所有権](../conventions/manuscript-claim-ownership.md) に入った。 以下は提案時の記録。

## <a id="hole"></a>穴

[§5 の限界](../conventions/manuscript-claim-ownership.md#limits) にある経路。 保護領域の外にある `\input` の行を消す (コメントにする・別の file に向け直す) commit は、 その行がどの保護領域にも入らないので止まらない。 次の commit からは、 外した子原稿 (abstract の無い `.tex`) が HEAD・index・作業ツリーのどの到達範囲にも無いので範囲の外になり、 中の序論・結論・数式を承認なしに書き換えられる。

## <a id="fix"></a>塞ぎ方

1 段目の commit で止める。 commit の前 (HEAD) と後で、 読み込みの到達範囲 (abstract を持つ `.tex` から `\input` 系で辿れる file) を比べる (`reach_changes`)。

- **外れる file** (HEAD で到達範囲に入り、 commit の後も在るのに到達範囲に無い) = その file の HEAD の全領域の **delete**。 承認は子原稿の path で取る (`approve --file <子原稿> --region …`)。
- **入る file** (HEAD に在って到達範囲に無く、 commit の後に入る、 abstract の無い file) = commit の後の全領域の **add**。 依頼の範囲の外にある対称の穴 (原稿に入っていなかった file の式を `\input` の 1 行で原稿に足す) を塞ぐ。 移動の扱いの「新しい path にだけ在る領域は add」 と同じ考え方。 不要なら、 この半分だけ落とせる (下の [強まる点](#stricter) 2)。
- commit の後の版: 既定 (index) は index、 作業ツリーを含む commit (`-a` / `-- <path>` / 同じ command の `git add`) は index に、 commit に入る path だけ作業ツリーの版を重ねる (`commit_tex_texts`)。 PreToolUse(Bash) と git pre-commit が同じ関数 (`changes_for_repo`) を通る。
- commit で消える file・現れる file は比べない (削除・追加・移動は従来の path ごとの比較と `moved_changes` が持つ)。 だから子原稿の移動と親の `\input` の書き直しを同じ commit に入れた正当な付け替えは、 従来どおり 0 件。
- 範囲を設定の `include` で決める repo (読み込みに依らない)・`disabled`・`exclude` の file は見ない。 全部の設定が `include` / `disabled` なら版の `.tex` を読みに行かない。 `.tex` を含まない commit も見ない。
- engine の構造上の変更: `input_graph` を版の中身 (`tex_texts`、 cache) と到達範囲 (`tex_reach`) に分けただけ。 既存の呼び出しの結果は変わらない。

## <a id="design-choices"></a>設計の判断と捨てた案

- **捨てた案: 範囲を「履歴のどこかで読み込みに入っていた file」 に広げる** (2 段目の commit で止める形)。 commit のたびに過去の版を辿る費用が file 数と履歴の長さに比例し、 hook の timeout で素通りする側に倒れる ([§5 の hook の timeout](../conventions/manuscript-claim-ownership.md#limits))。 本人が意図して外した後も子原稿が保護され続ける (外す裁定が効かない)。 1 段目で止めれば 2 段目は起きないので、 こちらを採った。
- **捨てた案: 編集 hook で親の `\input` の書き換えを止める**。 子原稿を `git mv` する前に親を直すと、 その時点では移動先がまだ無く「外れた」 に見えて、 正当な移動を順番だけで止める。 commit の時点なら移動の組と同時に判定できて、 順番に依らない。
- **commit の後の版は index に作業ツリーの版を重ねて正確に作る**。 移動の判定が使う「index と作業ツリーの到達範囲の共通部分」 は狭めの近似で、 外れる file の判定に使うと、 commit に入らない作業ツリーの変更で外れたように見えて誤って止める。
- **読み込みに入る側は abstract の無い file に限る**。 abstract を足した file は他の原稿に入るのでなく自分が原稿の起点になるので、 その abstract の追加は従来どおり止まる。 既存の本文まで全部「追加」 にすると、 「この note に abstract を付けて」 という依頼で無関係な式まで承認が要る。
- **`include` / `disabled` の repo では版の `.tex` を読みに行かない**。 範囲が読み込みに依らない repo に、 HEAD と index の全 `.tex` を読む経路 (読めなければ fail-closed で止まる) を新しく増やさない。
- **外れる・入る file の範囲の判定は、 その file だけを `include` に入れて比べる**。 到達範囲の差で範囲に入ることは決まっている。 既存の範囲の判定 (HEAD・index・作業ツリーそれぞれの到達範囲の和) を通すと、 `-- <path>` の commit のように版を組み合わせた形で、 黙って範囲の外に落ちる場合がある。

## <a id="looser"></a>緩む点

- **読み込みに入る file を同じ commit で書き換えたとき、 その file の旧い版にだけ在った領域の delete は出なくなる。** 従来は index の到達範囲で範囲に入るので旧い版 → 新しい版の比較が走り、 旧い版の領域の delete も出ていた。 置き換え後は全領域の add だけ。 旧い版は HEAD で到達範囲の外 = 保護されていなかったので、 保護が減るわけではない (従来の delete は過剰だった)。
- 外れる file を同じ commit で書き換えたとき、 新しい版にだけ在る領域の add は出なくなる (新しい版は commit の後に範囲の外 = 保護されない)。 代わりに HEAD の全領域の delete が出るので、 承認の範囲は狭まらない。
- 述語として通るようになる commit は無い。

## <a id="stricter"></a>強まる点

1. 保護領域の外の `\input` の行を消す・コメントにする・別の file に向け直す commit が、 外れた子原稿の全領域の delete で止まる (本件)。
2. 原稿に入っていなかった既存の file (abstract の無いもの) を `\input` で読ませる commit が、 その file の全領域の add で止まる (対称の穴)。
3. 親の移動で子原稿の読み込み先が解決できなくなる commit は、 従来の親の path ごとの finding に加えて、 子原稿の delete も出る (承認の件数が増える。 結論は従来どおり止まる)。
4. 旧い子原稿を残したまま複製に向け直す commit は、 複製の add (従来) に加えて旧い子原稿の delete も出る (§3 の「旧い path を残す複製は両方を記録」 と同じ形になる)。

## <a id="tests"></a>試験の結果

engine の `--selftest` に 6c の fixture を 10 件足した (git repo の外の複製で実行)。

| 版 | 結果 |
|---|---|
| 直す前の engine + 新しい fixture | **FAILED 7** (外す 5 件・向け直し 1 件・入れる 1 件。 下の「止めない」 2 件と承認で通す 1 件は、 直す前は何も出ないので緑) |
| 直した engine + 新しい fixture | **ALL PASS** (ok 454 件。 直す前の engine 単体は ok 444 件で ALL PASS) |

足した fixture (止める側):
- `\input` の行を消す commit = 子原稿の `intro` と `eq:uv` の delete。 未承認の pre-commit は exit 1 で子原稿を名指す。 `git commit -a` も同じ。
- 子原稿の path で記録した承認があれば pre-commit は exit 0。
- `\input` をコメントにして親だけを `git commit -- <親>` で出す経路 (PreToolUse の `commit_targets`) も同じ。
- 旧い子原稿を残す複製へ向け直す = 旧い子原稿の delete と複製の add の両方。
- 原稿に入っていなかった既存の file を読ませる = その file の式の add。

足した fixture (止めない側 = 強めすぎの確認):
- 外しても別の原稿が読み続ける子原稿と、 保護領域を持たない子原稿 = 0 件。
- 範囲を `include` で決める repo = 0 件 (子原稿は glob で範囲に残る)。

既存の移動の fixture (子原稿の移動 + 親の `\input` の書き直しを同じ commit = 0 件、 dir ごとの移動 = 0 件、 git の呼び出し回数を file 数で比べる検査) は全部緑のまま。

## <a id="doc-draft"></a>文書の文案 (conventions/manuscript-claim-ownership.md)

**§2「原稿の範囲」 の最後の文** (現在「HEAD・index・作業ツリーの到達範囲の和を取り、参照を外しても元の子原稿の保護を失わない。」) を次に置き換える:

> HEAD・index・作業ツリーの到達範囲の和を取る。 commit の前 (HEAD) と後で到達範囲が変わる file は、 外れる file (commit の後も在るもの) を HEAD の全領域の削除、 入る既存の file (abstract の無いもの) を commit の後の全領域の追加として比べる。 保護領域の外の `\input` の行を消す・コメントにする・別の file に向け直す commit は、 外れる子原稿の領域で止まる。 削除・追加・移動される file はこの比較に入れない (path ごとの比較と移動の扱いが持つ)。 範囲を `include` で決める repo は読み込みに依らないので見ない。

**§3 の最後の文** (「`\input` の行を消すと、 その行を含む節の変更として数える。」) の後に足す:

> 保護領域の外の行でも、 子原稿が原稿の読み込みから外れれば、 その子原稿の全領域の削除として数え、 記録は子原稿の path で取る (`--file <子原稿>`)。 原稿に入っていなかった既存の file を読み込む行を足すと、 その file の全領域の追加として数える。

**§5「子原稿を読み込みから外す 2 段の経路」 の項** を次に置き換える:

> - **子原稿の読み込みを外す編集そのもの**: 編集 hook は親の `\input` の行の書き換えを止めない (子原稿を先に動かすか親を先に直すかの順番で、 正当な移動を誤って止めないため)。 外れたかは commit の時点で、 HEAD と commit の後の到達範囲を比べて判定する。 外す commit を人が terminal で出した後は、 子原稿は範囲の外になる (人の判断)。 `\input` を macro で包む書き方は最初から辺として読まないので、 その子原稿は初めから範囲の外 (従来どおり)。

engine の docstring (「何を止めるか」 1.) にも同じ趣旨の 3 行を足した (差分に含む)。

## <a id="residual"></a>残る限界

- 編集 hook (Edit / apply_patch) の時点では止めない (上の §5 の文案)。 編集から commit までの間、 子原稿は HEAD の到達範囲で範囲に残るので、 その間の子原稿の編集は従来どおり止まる。
- 到達範囲の辺は `input_children` の読み方のまま (`\iffalse` の中の `\input` も辺として読む = 止めすぎの側。 macro で包んだ `\input` は読まない = 初めから範囲の外)。

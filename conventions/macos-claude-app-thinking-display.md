<!-- doc-meta
when: Claude for Mac (desktop / Code タブ) で思考 (thinking) の要約が画面に出ない・「考え中」 / 「思考」 の表示が見つからないとき + 思考の表示を既定にしたいとき + settings.json の showThinkingSummaries が desktop で効くか判断する前
category: macos
summary: desktop app は画面が「思考」 表示でないセッションを --thinking-display omitted で起動し、 表示を切り替えた時点から要約を要求する (前のターンは署名だけで後から出ない)。 起動引数が settings.json の showThinkingSummaries を上書きするので desktop ではその setting は効かない。 切替 = タイトル横の ⌄ → トランスクリプト表示 → 思考 / 思考をデフォルトにする (右上の ⋮ から移った、 日本語 UI は英語の Transcript view / Thinking と訳語が違う)。 画面と app 本体が噛み合わないと切替が本体に届かない → ウィンドウ再読み込み。 一発診断 = scripts/claude-app-thinking-diagnose.py
-->
# Claude for Mac で思考の要約が出ない — 仕組みと切り分け

Code タブで思考 (thinking) の要約が画面に出ないのは、 多くの場合 **不具合でなく app の作り** による。 読んだ版 = app 2.9939.2 / 埋込 engine 2.1.281 (挙動は版で変わるので、 別の版では [`claude-app-bundle-reading.md`](claude-app-bundle-reading.md) の手順で読み直す)。 一発診断 (read-only) = [`scripts/claude-app-thinking-diagnose.py`](../scripts/claude-app-thinking-diagnose.py)。

## <a id="on-demand-summaries"></a>仕組み: 思考の要約は「思考」 表示にした時点から要求される

- app は、 画面が「思考」 表示でないセッションの engine を **`--thinking-display omitted`** 付きで起動する。 API は思考の本文を返さず、 transcript (jsonl) の thinking block は **本文が空で署名だけ** になる。
- 画面を「思考」 表示にすると、 app が engine に切替の control request (`set_max_thinking_tokens` の `thinking_display: "summarized"`) を送る。 app の log (`~/Library/Logs/Claude/main*.log`) に `[CCD] thinking display → summarized (view_open)` が出る。 表示を戻すと少し待ってから `→ omitted (view_close_debounce)`。
- 効くのは **次の応答から** (画面の文言にも「次の回答から思考の要約が表示されます。」 がある)。 **切り替える前のターンの思考は受け取っていないので、 後から表示を変えても出ない**。
- 起動引数は起動時の値のまま残る = 後で「思考」 に切り替えたセッションも `ps` では `omitted` と見える。 効いたかは log の view_open と、 以後の thinking block に本文があるかで見る。

## <a id="settings-json-ignored"></a>desktop では settings.json の `showThinkingSummaries` は効かない

engine は思考の表示を「起動引数 `--thinking-display` → settings.json の `showThinkingSummaries`」 の順で決める (同梱 engine のコードで確認)。 desktop は起動引数を必ず渡すので、 **setting は上書きされる**。 CLI (terminal) では setting が効く。 desktop で常に出したいなら、 次節の「思考をデフォルトにする」 を使う。

## <a id="where-in-ui"></a>画面のどこで切り替えるか

- **セッションのタイトル横の「⌄」 →「トランスクリプト表示」 →「通常 / 思考 / 詳細」**。 同じ submenu の **「思考をデフォルトにする」** で新しいセッションの既定になる (= 起動時から要約を受け取る)。
- 以前は右上の「⋮」 にあった項目群がタイトル横の「⌄」 に移った (公開 issue [anthropics/claude-code#95697](https://github.com/anthropics/claude-code/issues/95697))。 サイドバーのセッション行の「⋮」 はピン留め・アーカイブ等で、 表示の切替は無い。
- **英語と日本語で名前が違う**: Transcript view = 「トランスクリプト表示」、 Normal / Thinking / Verbose = 「通常 / 思考 / 詳細」。 `Thinking` の訳語は「考え中」 と「思考」 が併存し、 メニューは「思考」。 app の tool 説明 (`mcp__ccd_view__set_transcript_view`) は英語名で書かれているので、 **user に場所を案内する前に訳語を `claude-app-bundle.py i18n "<英語名>"` で引く**。
- Claude 自身は `mcp__ccd_view__set_transcript_view` (`view: "thinking"`) で自分のセッションと自分が起こした子のセッションを切り替えられる。 それ以外のセッションは user がそのセッションのメニューから。

## <a id="stale-renderer"></a>切り替えが本体に届かないとき: 画面と app 本体の噛み合い

- 画面にセッションが出ているのに `mcp__ccd_view__get_layout` が **「どのウィンドウにも開かれていない」** (`views: []`) と答える = 画面 (renderer) が app 本体に表示状態を報告していない。 この状態では画面で表示を変えても本体の切替 (log の view_open) が起きない。
- 実測: ウィンドウの再読み込み (メニューバー「表示」 → 再読み込み) で `views` が返るようになり、 切替が届いた。 app を長く起動したままのときに起きやすい。

## <a id="diagnose"></a>切り分けの順序

1. `python3 scripts/claude-app-thinking-diagnose.py` (版 / engine の起動引数 / log の切替記録 / transcript の本文あり比率 / settings.json)。
2. 起動引数が `omitted` ∧ log に view_open が無い → 画面が「思考」 表示になっていない。 [#where-in-ui](#where-in-ui) で切り替える。
3. 画面は「思考」 なのに view_open が出ない → [#stale-renderer](#stale-renderer)。
4. view_open が出た後の thinking block にも本文が無い → 版の違いか別の原因。 [`claude-app-bundle-reading.md`](claude-app-bundle-reading.md) で `thinking-display` を `--where asar` / `--where engine` から読み直す。

## <a id="pitfalls"></a>落とし穴

- **「メニューに無い」 と言われたら、 どのメニューかを先に特定する**。 実測: 候補 (タイトル横の ⌄ / 右上の ⋮ / サイドバー行の ⋮ / メニューバー) を並べずに「消えた不具合」 と推定して、 案内が 2 往復ずれた。 画面の文言は i18n と renderer にあるので、 推定より先に読める。
- **Claude は自分が動いている app の画面を computer-use で見られない** (許可を求められる app の一覧に出ない)。 画面の確認は user のスクリーンショットに頼る = どのメニューを開いた状態を写してほしいかを指定する。
- **表示の切替は既定値の setting ではない**。 セッションごとの表示は `set_transcript_view`、 新しいセッションの既定は user が「思考をデフォルトにする」 で決める。

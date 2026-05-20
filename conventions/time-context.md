# Time context — currentDate anchor 規律

Claude は session 開始時に `# currentDate` context を持っているが、 multi-turn / multi-day session で user 発話の「今日 / 明日 / 今夜 / 明朝」 等の時刻 deictic 表現を、 **会話の流れで暗黙に旧 frame (= 「前ターンの仮想 today」) で解釈する reflex failure** を起こすことがある。

## 規律

**1.** Claude (= 私) は user 発話の時刻 deictic 表現を解釈する際、 **必ず currentDate を起算点**として再翻訳する。 「会話の流れ」 「前ターンの仮想 today」 「session 開始時に想定した today」 等の 暗黙 frame で解釈しない。

**2.** 「今日 / 明日 / 昨日 / 今夜 / 明朝 / 明後日 / 先日 / 翌日 / 今週 / 来週 / 先週 / today / tomorrow / yesterday / tonight / last week / next week / in N days / N days ago」 等の表現を user が使ったとき、 chat 応答で **何月何日 (曜日) に対応するか明示**する。 暗黙に解釈して進めない。

**3.** 機械的 enforcement: `claude-config/hooks/currentdate-anchor.py` が UserPromptSubmit + SessionStart hook として動作:
- **UserPromptSubmit**: user prompt に時刻 deictic 表現が含まれていたら system reminder で currentDate + relative dates (今日 / 明日 / 昨日 / 明後日) を inject
- **SessionStart**: session 開始時に無条件で currentDate を inject

規律 (1)(2) を wording で書いても Claude の reflex で skip されるため、 hook で機械的に inject (= `odakin-prefs/CLAUDE.md inline §15 axis 2`「文書 aspirational instruction と実装の drift を避ける、 実装側で強化」 の考え方を適用)。

## 設計理由 (= 2026-05-19→20 RCA)

odakin の session で、 currentDate = 2026-05-20 だったが、 Claude (= 私) は前ターンの user 発話「今日はもう帰るけど、 あした学生本人にメール書こう」 を 5/19 frame で受け取り、 「明日 = 5/20、 明朝の draft 着手で十分」 等と発話した。 真実は currentDate = 5/20 で「今日 = 5/20、 明日 = 5/21」、 時刻 frame が 1 日ずれていた。 古川さん経緯説明メールの〆切は 5/20 (= 今日) で 切迫していたのを user 指摘「もうその明日や」 で発覚。

これは odakin-prefs/CLAUDE.md inline §16「context 構築での単一情報源 null 結論飛躍」 trait family の **時刻 domain での現れ**: 「user 発話の『明日』」 という 単一観察 (= 言語表現) を、 currentDate context を bypass して「会話流れ」 で解釈 (= cell 埋め)、 実際の時刻 anchor (= currentDate) を expose せず暗黙化。 「不確実性を expose か隠すか」 の問いで「隠す」 を選んだ assertion。

## 失敗 / 修復のメタ規律

- `currentDate` が context にあっても reflex で skip される (= context 持っている ≠ 都度参照する) → hook で **explicit refresh + interpretive hint inject**
- false positive (= 「明日香」 等の地名で hit) は実害低い (= Claude が currentDate を 1 回多く見るだけ)、 false negative (= 時刻表現検出失敗で frame ずれ) はコスト高い → **false positive 許容、 false negative 最小化**で広めの pattern

## 関連

- `~/Claude/odakin-prefs/CLAUDE.md inline §16` (= 単一情報源 null 結論飛躍、 時刻 domain への現れ)
- `claude-config/hooks/currentdate-anchor.py` (= 実装本体)
- `claude-config/hooks/pdf-read-fallback-nudge.sh` (= 同じ「機械的 enforcement layer」 design pattern の前例、 2026-05-18 RCA)

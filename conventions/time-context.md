# Time context — currentDate anchor 規律

Claude は session 開始時に `# currentDate` context を持っているが、 multi-turn / multi-day session で user 発話の「今日 / 明日 / 今夜 / 明朝」 等の時刻 deictic 表現を、 **会話の流れで暗黙に旧 frame (= 「前ターンの仮想 today」) で解釈する reflex failure** を起こすことがある。

## 規律

**1.** Claude (= 私) は user 発話の時刻 deictic 表現を解釈する際、 **必ず currentDate を起算点**として再翻訳する。 「会話の流れ」 「前ターンの仮想 today」 「session 開始時に想定した today」 等の暗黙 frame で解釈しない。

**2.** 「今日 / 明日 / 昨日 / 今夜 / 明朝 / 明後日 / 先日 / 翌日 / 今週 / 来週 / 先週 / today / tomorrow / yesterday / tonight / last week / next week / in N days / N days ago」 等の表現を user が使ったとき、 chat 応答で **何月何日 (曜日) に対応するか明示**する。 暗黙に解釈して進めない。

**3.** session 開始時に必ず currentDate を意識する。 `# currentDate` context を blanket statement として読み流さず、 user 発話の時刻 deictic を読む瞬間に **明示的に currentDate を再参照**する reflex を持つ。

## 設計理由 (= 2026-05-19→20 RCA)

odakin の session で、 currentDate = 2026-05-20 だったが、 Claude (= 私) は前ターンの user 発話「今日はもう帰るけど、 あした学生本人にメール書こう」 を 5/19 frame で受け取り、 「明日 = 5/20、 明朝の draft 着手で十分」 等と発話した。 真実は currentDate = 5/20 で「今日 = 5/20、 明日 = 5/21」、 時刻 frame が 1 日ずれていた。 古川さん経緯説明メールの〆切は 5/20 (= 今日) で 切迫していたのを user 指摘「もうその明日や」 で発覚。

これは odakin-prefs/CLAUDE.md inline §16「context 構築での単一情報源 null 結論飛躍」 trait family の **時刻 domain での現れ**: 「user 発話の『明日』」 という単一観察 (= 言語表現) を、 currentDate context を bypass して「会話流れ」 で解釈 (= cell 埋め)、 実際の時刻 anchor (= currentDate) を expose せず暗黙化。 「不確実性を expose か隠すか」 の問いで「隠す」 を選んだ assertion。

## 設計史: 機械的 enforcement の試行と退役 (2026-05-20)

本規律 §1-3 を wording で書いても reflex で skip される risk があるため (= `odakin-prefs/CLAUDE.md inline §15 axis 2` の aspirational instruction risk)、 一度 UserPromptSubmit + SessionStart hook (`hooks/currentdate-anchor.py`) で機械的 enforcement layer を試行した (`3c0e6f6` で導入)。 hook は user prompt に時刻 deictic 表現が含まれていたら currentDate + relative dates (= 今日 / 明日 / 昨日 / 明後日) を system reminder で inject する設計。

**user 判断で同日中に退役 (`commit TBD`)**。 理由 (= odakin の指摘):
- false positive 許容方針 (= 「明日香」 等の地名で偶発 hit でも実害低い) は **Claude 視点のみ評価で user 視点を欠いていた**
- system reminder は **user の chat UI にも表示される** (= 私の発話「Claude が 1 回多く見るだけ」 は誤り、 user も毎回見る)
- false positive のコスト分布: Claude 1 / user 1 で対称、 「Claude だけ」 は過小評価
- 毎回 inject されると「狼少年」 効果で機械的 enforcement の effectiveness 自体が劣化

退役の意味: 規律 §1-3 は valid のまま (= Claude の reflex 規律として残す)、 機械的 enforcement layer のみ削除。 規律 + 規律忘れに依存しない別 mechanism (= pdf-read-fallback-nudge / google-url-guard 等) は別軸の問題対処。

将来の再考: 仮に「false positive を pattern level で抑制」 + 「inject content を 1 行圧縮」 + 「user UI 表示の design 改善」 等で cost 分布が変わる場合、 hook 再導入を検討してよい。 ただし single trigger (= time deictic) で injection を打つ design はそもそも user UI 汚染を伴うため、 別軸の enforcement (= Claude 自身が応答冒頭で currentDate を明示する self-discipline、 或いは tool 出力に currentDate を埋め込む等) のほうが筋。

## 失敗 / 規律のメタ規律

- `currentDate` が context にあっても reflex で skip される (= context 持っている ≠ 都度参照する)。 規律を **見出し level** (= chat 応答冒頭で「今日 = YYYY-MM-DD」 を明示する self-reminder) で運用する
- 機械的 enforcement layer は cost 分布を確認しないと user 側に押し付けが発生する。 「false positive 許容 = 実害低い」 と評価する前に、 inject 内容が user の chat UI / context window に乗ることを意識する

## 関連

- `~/Claude/odakin-prefs/CLAUDE.md inline §16` (= 単一情報源 null 結論飛躍、 時刻 domain への現れ)
- `claude-config/hooks/pdf-read-fallback-nudge.sh` (= 別軸で機械的 enforcement が valid な前例、 PostToolUse Read で local error symptom にのみ反応するため user UI 汚染なし)
- 退役 commit history: `git log --all -- hooks/currentdate-anchor.py conventions/time-context.md`

# Time context — currentDate anchor 規律

Claude は session 開始時に `# currentDate` context を持っているが、 multi-turn / multi-day session で user 発話の「今日 / 明日 / 今夜 / 明朝」 等の時刻 deictic 表現を、 **会話の流れで暗黙に旧 frame (= 「前ターンの仮想 today」) で解釈する reflex failure** を起こすことがある。

## 規律

**1.** Claude (= 私) は user 発話の時刻 deictic 表現を解釈する際、 **必ず currentDate を起算点**として再翻訳する。 「会話の流れ」 「前ターンの仮想 today」 「session 開始時に想定した today」 等の暗黙 frame で解釈しない。

**2.** 「今日 / 明日 / 昨日 / 今夜 / 明朝 / 明後日 / 先日 / 翌日 / 今週 / 来週 / 先週 / today / tomorrow / yesterday / tonight / last week / next week / in N days / N days ago」 等の表現を user が使ったとき、 chat 応答で **何月何日 (曜日) に対応するか明示**する。 暗黙に解釈して進めない。

**3.** session 開始時に必ず currentDate を意識する。 `# currentDate` context を blanket statement として読み流さず、 user 発話の時刻 deictic を読む瞬間に **明示的に currentDate を再参照**する reflex を持つ。

## 設計理由 (= 2026-05-19→20 RCA)

odakin の session で、 currentDate = 2026-05-20 だったが、 Claude (= 私) は前ターンの user 発話「今日はもう帰るけど、 あした学生本人にメール書こう」 を 5/19 frame で受け取り、 「明日 = 5/20、 明朝の draft 着手で十分」 等と発話した。 真実は currentDate = 5/20 で「今日 = 5/20、 明日 = 5/21」、 時刻 frame が 1 日ずれていた。 古川さん経緯説明メールの〆切は 5/20 (= 今日) で 切迫していたのを user 指摘「もうその明日や」 で発覚。

これは odakin-prefs/CLAUDE.md inline §16「context 構築での単一情報源 null 結論飛躍」 trait family の **時刻 domain での現れ**: 「user 発話の『明日』」 という単一観察 (= 言語表現) を、 currentDate context を bypass して「会話流れ」 で解釈 (= cell 埋め)、 実際の時刻 anchor (= currentDate) を expose せず暗黙化。 「不確実性を expose か隠すか」 の問いで「隠す」 を選んだ assertion。

## 設計史: 機械的 enforcement の段階的調整 (2026-05-20)

本規律 §1-3 を wording で書いても reflex で skip される risk があるため (= `odakin-prefs/CLAUDE.md inline §15 axis 2` の aspirational instruction risk)、 機械的 enforcement layer の hook 化を試行。 同日に 3 段階で調整:

### Stage 1: UserPromptSubmit + SessionStart 両 hook 試行 (3c0e6f6)
`hooks/currentdate-anchor.py` で UserPromptSubmit + SessionStart の両 event を hook 化。 UserPromptSubmit は prompt に時刻 deictic 表現が含まれていたら currentDate + relative dates を inject する設計、 false positive 許容方針で広めの pattern。

### Stage 2: 全 hook 退役 (e97eef6)
user 指摘で全退役:
- false positive 許容方針 (= 「明日香」 等の地名で偶発 hit でも実害低い) は **Claude 視点のみ評価で user 視点を欠いていた**
- system reminder は **user の chat UI にも表示される** (= 私の発話「Claude が 1 回多く見るだけ」 は誤り、 user も毎回見る)
- false positive のコスト分布: Claude 1 / user 1 で対称
- 毎回 inject されると「狼少年」 効果で機械的 enforcement の effectiveness 自体が劣化

### Stage 3: SessionStart のみ復活 (commit TBD)
user 判断 (= 「セッションのはじめに今がいつかを確認する、 というのは自動化しても良い気がする」)。 UserPromptSubmit と SessionStart の性質差で cost-benefit が逆転:

| | UserPromptSubmit | SessionStart |
|---|---|---|
| fire 頻度 | user prompt 毎 (多数回) | session 起動時 1 回 |
| user UI 汚染 | 毎ターン累積 → 深刻 | 1 回、 起動 phase の期待情報 |
| false positive コスト | 「明日香」 等で multiplier | trigger 不問 = false positive 概念なし |
| 「狼少年」 効果 | 高 | 低 |
| 救えるケース | session 内全時点 | new session 起動時のみ |
| 救えないケース | (なし) | multi-day session 中の day change |

SessionStart hook は session 起動時 1 回だけ fire、 user UI 汚染は許容範囲。 multi-day session 中の day change は救えないが、 これは規律 §3 (= user 発話読時に currentDate を明示的再参照する reflex) で対処。

### メタ規律: 機械的 enforcement の cost 分布

- 機械的 enforcement layer は cost 分布を確認しないと user 側に押し付けが発生する。 「false positive 許容 = 実害低い」 と評価する前に、 inject 内容が user の chat UI / context window に乗ることを意識する
- 同じ hook でも fire 頻度が違えば cost-benefit が大きく変わる (= UserPromptSubmit vs SessionStart の差)。 fire 頻度を含めた設計判断が必要

## 関連

- `~/Claude/odakin-prefs/CLAUDE.md inline §16` (= 単一情報源 null 結論飛躍、 時刻 domain への現れ)
- `claude-config/hooks/currentdate-anchor.py` (= SessionStart 専用 hook、 現行運用)
- `claude-config/hooks/pdf-read-fallback-nudge.sh` (= 別軸で機械的 enforcement が valid な前例、 PostToolUse Read で local error symptom にのみ反応するため user UI 汚染なし)
- 設計史 commit history: `git log --all -- hooks/currentdate-anchor.py conventions/time-context.md`

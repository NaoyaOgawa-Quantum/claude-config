# Tool call robustness — Claude の tool 呼び出しが「malformed」 で壊れるのを防ぐ

> 適用対象: Claude が **任意の tool call (特に Bash / Edit)** を生成する全ての場面。 hook 作成に限らない。
> hook script を書くときの bash 3.2 parser bug は **別 layer** の話 (= `hook-authoring.md §1` 参照)。

---

## 現象

tool call が `Your tool call was malformed and could not be parsed. Please retry.` で失敗し、 retry も失敗すると `ターンが失敗しました` になる。 これは harness が **生成された tool call (構造化テキスト) を deserialize できなかった** failure であって、 危険操作の block ではない (= permission dialog / hook deny とは別物)。 実害は通常なし (= tool は実行されず状態は不変) だが、 user を待たせ session が止まる。 「やってはならない操作をした」 と誤解されやすいので、 発生時は **まず「フォーマットが壊れただけで何も実行・破壊していない」 と明示**する。

## 真因 (= 2026-06-05 調査で同定、 確度高)

**Anthropic backend 側の model serialization bug** (= 大きい context 長で動く Opus 系 model が tool_use block を構造的に壊れた形で出力する)。 報告環境は **Opus 4.8 の 1M-context session (macOS)**。 **Claude Code CLI の bug でも、 prompt の書き方の問題でもない**。 当初仮説 (= 後述「副次トリガー」 の特殊文字密集が *主因*) は誤りで、 root は model 出力側にある。

裏付け (= upstream issue tracker `anthropics/claude-code` に同症状の OPEN issue が複数、 いずれも model 側ラベル `area:model`):

| issue | 症状 | 環境一致 |
|---|---|---|
| #64684 | tool call の XML タグ prefix が脱落、 長い context の session で発生 | macOS / Opus 4.8 1M-context に一致 |
| #64955 | parallel tool call / 非 ASCII (日本語等) tool call で頻発 | 並列呼び出し + 日本語に一致 |
| #64235 | ある時期以降の regression、 stop_reason は tool_use なのに tool_use block 不在 | — |
| #62344 (副次機序) | 一度 malformed が context に入ると後続 tool call も壊れた形を複製する (= few-shot poisoning) | retry が連続失敗する説明 |

→ 特殊文字密集・装飾過多は **root ではなく、 poisoning density / 並列度を上げて発生確率を押し上げる副次条件** に過ぎない。

## 副次トリガー (= 発生確率を上げるだけ、 root ではない)

| トリガー | 例 | なぜ確率を上げるか |
|---|---|---|
| **並列 tool call** (1 ターンに複数の tool call) | 独立した Read を 1 ターンで複数発行 | #64955 が parallel を頻発条件に挙げる |
| **非 ASCII を多く含む tool call** | 日本語の長い本文・引数 | #64955 が non-ASCII を頻発条件に挙げる |
| Bash 内の **特殊文字密集** | 多段パイプ + 正規表現 (`grep -oE` で引用符を含むパターン)、 heredoc (`python3 - <<'PY' ... PY`)、 引用符の入れ子 | serialization の delimiter/escape と干渉、 poisoning density 上昇 |
| **CLI 引数に渡す JSON literal** (= 引用符の入れ子) | `node x.mjs '{"k":5}'` のように tool call で nested-quote JSON を生成 | nested quote が干渉しやすい。 → 引数なし default にする、 または args を file に書いて path だけ渡す |
| **長い本文 + markdown テーブル + 絵文字** の直後の tool call | 表 + 絵文字を詰めた長文応答の末尾に tool call | 装飾過多で生成 token 列が長大化 |

## 副次緩和 (= 発生確率を下げる運用、 root は直さない)

root は backend fix 待ちだが、 発生確率と poisoning ループは以下で下げられる:

1. **1 ターン 1 tool call を基本にする** (= 並列を避ける、 #64955 対策)。 独立タスクでも 1 つずつ発行する。
2. **複雑ロジックは `Write` でファイル化 → 単純コマンドで実行**。 Bash インラインの heredoc / 言語埋め込みは避ける (= 中間 file に書いて `python3 /tmp/x.py` で呼ぶ)。
3. **JSON / 正規表現 / 条件判定は script ファイルへ**。 grep / awk ワンライナーで無理に処理しない。 CLI に JSON literal を直接渡さず file path で渡す。
4. **tool call を含むターンは本文をプレーン短文に**。 markdown テーブル・大量絵文字は tool call の無い応答ターンに寄せる。
5. **`cd` を compound command に入れない** (= 別途 permission prompt を誘発)。 `git -C <dir>` 等で代替。
6. **commit message など複数行 + 山括弧を含むものはファイルに書いて `git commit -F`** で渡す (= `-m "..."` 内の山括弧・改行を避ける)。
7. **malformed が出たら同 session で retry を重ねない**。 #62344 の poisoning で後続も壊れるため、 数回失敗したら **新しい session に切り替える** (= 壊れた context を断ち切る)。

## 限界 (= 誇張しない)

- root は **Anthropic backend の model serialization bug** であり、 **prompt の書き方変更でも narrative でも直らない**。 上記「副次緩和」 は発生確率を下げるだけで 0 にはできない。
- hook での機械 enforcement も困難 (= 生成前の self-gate であり、 `hook-authoring.md §5.1` の単一視点 self-reference 不能と同型)。 本 file は memory aid であって enforcement ではない、 という前提で読むこと。
- **fix は upstream (Anthropic) 待ち**。 上記 issue 番号を追跡し、 解決報告が出たら「副次緩和」 を緩められる。 CLI を新しめの版に上げると retry handling が改善する可能性はあるが、 **root (model 出力) は version 更新では消えない** (= CLI 2.1.165 の改善効果は未検証、 retry handling 改善の可能性のみ)。

## メタ規律 (= なぜ当初 root を読み違えたか)

最初の RCA は原因を「特殊文字の密度」 = **自分で制御できる writing-style 要因** に帰属させた。 自分の操作で塞げる原因の方が actionable なので、 そちらに飛びつくバイアスがある。 だが実際は **外部 (backend model) の bug** で、 別 session で書き方を整えても再発した — この「書き方を変えても消えない」 という観察こそが root が自分の外にある signal だった。 **書き方変更で消えない再発は、 自分の挙動でなく tool/backend を疑う** へ早く切り替える (= 表層の writing-style モグラ叩きで時間を溶かさない)。

## Rotted-session knowledge recovery — malformed-bug で死んだ session の知見回収

malformed-tool-call bug で session が**途中で死んでも、 その session が積んだ知見は回収可能**である (= 上記「副次緩和 7」 で新 session に切り替えた後、 死んだ session を捨てずに knowledge salvage する手順)。 死んだ session には (a) chat に出ただけで file に未保存の知見と、 (b) 完了したが報告前に死んだ作業、 の 2 種が残りうる。 両方を別経路で拾う:

1. **死んだ session の transcript を locate する**: Claude Code は session の実体を JSONL transcript として保存している。 harness (= CCD) では Application Support 配下の `local_<id>.json` は **thin wrapper** なので、 まずこれを read して中の `cliSessionId` を得る → 実体の JSONL は `~/.claude/projects/<project-dir>/<cliSessionId>.jsonl` にある (= `<project-dir>` は作業ディレクトリを encode した名前)。
2. **gap-analyze する**: transcript に残る知見と、 **既に files に persist 済みの内容との差分**を取る (= chat には出たが doc / SESSION に書かれずに死んだ insight を surface する)。 durable な home (= 該当 doc / SESSION / plan) へ記録して回収完了。
3. **完了済だが報告前に死んだ作業は `git log` で確認する**: malformed が報告 (= chat への完了報告) の直前に起きると、 commit は済んでいるのに「やった」 と言えずに session が死ぬ。 当該 session の `git log` を読めば実際に commit された作業が分かる (= **知見と commit は別 artifact**、 transcript salvage と git log の両方を拾う)。

⚠️ root が backend bug である以上、 この回収手順は「死を防ぐ」 ものではなく「死んだ後に損失を最小化する」 ものである (= 「限界」 section と整合、 新 session 切り替えとセットで運用する)。

## 関連

- `hook-authoring.md §1` — bash 3.2 の `$(...)` + heredoc parser bug。 **別 parser** (= macOS stock bash) だが回避策 (中間 file 化) が共通。
- `hook-authoring.md §5.1` — 単一視点 self-reference の geometric 不能 (= 本 file「限界」 section の理論的根拠)。

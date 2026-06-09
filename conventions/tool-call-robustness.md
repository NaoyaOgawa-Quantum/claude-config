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

### Canonical issue と報告先 (= 2026-06-10 調査で同定)

上表の issue は実は**衛星** (= いずれも `duplicate` ラベル付き)。 集約先の **canonical issue は #62123** (= `duplicate` ラベルが付いていない唯一の主要 issue、 area:model、 コメント欄でクラスタ #62123/#62344/#62467/#62700/#49747 が cross-reference されているハブ)。 #63875 (56 comments) はコメント数最大だがそれ自体 duplicate 扱い。 **新たな occurrence を報告するときは新規 issue を立てず #62123 にコメント**する (= 重複 issue はノイズ、 新しい trigger profile / 頻度 data point のみ価値がある)。 また **#64774 が model 別の失敗率を定量報告** (= `claude-opus-4-8` ~1.5% / `opus-4-7` と `sonnet-4-6` は 0%) しており、 bug が Opus 4.8 固有であることの強い証拠。

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
8. **model を切り替える** (= 最も確実な緩和)。 bug は Opus 4.8 固有で、 #64774 が他 model (Opus 4.7 / Sonnet 4.6) の失敗率 0% を定量報告。 tool-call 密度の高い作業で頻発するなら `/model` で別 model に切り替えるのが root に最も近い回避になる (= backend fix が出るまでの実用解)。

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
4. **stale handoff plan vs working tree の罠** (= 2026-06-10 実例): 死にかけの session が「未解決の問い X の handoff plan」 を commit した**後**に、 working tree へ X に関する draft 編集を残して死ぬことがある (= 意図的に uncommit のまま残した場合もある — 例: cold-eyes の判断を pre-empt しないため revert しようとした compound command 自体が malformed で死に、 revert されず残留)。 このとき **plan の「open」 framing と working tree の編集内容が食い違って見える**。 回収する新 session は (a) plan を読む前にまず `git status` + `git diff` で working tree を確認する、 (b) 「掃除」 のつもりで `git restore` / `checkout --` による blind discard をしない (= 死んだ session の成果や意図的 draft が消える)、 (c) 食い違いは「tree の方が新しい」 という証拠として扱い、 どちらを正とするかは内容で判断する。 また compound command (`revert && commit && push` 等) が malformed で死んだ場合、 **部分実行か全不実行かは不明**なので、 意図された各効果 (revert されたか / commit されたか / push されたか) を個別に検証する。

⚠️ root が backend bug である以上、 この回収手順は「死を防ぐ」 ものではなく「死んだ後に損失を最小化する」 ものである (= 「限界」 section と整合、 新 session 切り替えとセットで運用する)。

## 別の Bash 失敗モード: 出力 capture の ENOSPC (= 「Command output was lost」、 malformed とは別物)

malformed (= model serialization bug) とは独立の失敗で、 **Bash tool の stdout/stderr が harness に capture されず失われる**ことがある。 症状: tool result が `Command output was lost: the temp filesystem at /private/tmp/claude-<uid>/.../tasks is full (0MB free). ... ENOSPC` になる。 ⚠️ **コマンド自体は実行されている可能性が高い** (= 出力の取りこぼしであって操作の失敗ではない) ので、 「失敗した」 と即断せず別経路で結果を確認する。

- **真因**: harness が child の stdout/stderr を一時 file に capture するが、 その capture 用 filesystem が満杯。 **メインディスクの空きとは独立** (= `df -h` でルートに余裕があっても capture fs だけ 0MB になりうる)。 正確な trigger は未確定 (= 多数 session 分の temp 累積等の可能性、 単一観察)。
- **workaround (確実)**: コマンドの出力を **余裕のある fs 上の file に redirect し、 自身の stdout を空にする** → harness の capture write が空 (or 極小) になり ENOSPC を回避 → その file を `Read` で読む。

```bash
some-cmd > /abs/path/out.txt 2>&1; true   # stdout を出さない。 末尾 true で exit 0 を保証
```

  その後 `Read /abs/path/out.txt`。 **出力を持たないコマンド (= `rm` 等) はそのまま成功する**ので、 free-up 系はそのまま実行できる。
- `CLAUDE_CODE_TMPDIR` を余裕のある dir に向ければ capture 先を移せるが、 **harness は親プロセス env から読む**ため child の Bash 内で export しても効かない (= 設定変更は session 再起動が要る)。
- 上記「副次緩和 2」 (複雑ロジックを `Write` で file 化) と相性がよい: script を file 化 → `bash script > out.txt 2>&1` → `Read` で、 **malformed と ENOSPC の両方を同時に回避**できる。

## 関連

- `hook-authoring.md §1` — bash 3.2 の `$(...)` + heredoc parser bug。 **別 parser** (= macOS stock bash) だが回避策 (中間 file 化) が共通。
- `hook-authoring.md §5.1` — 単一視点 self-reference の geometric 不能 (= 本 file「限界」 section の理論的根拠)。

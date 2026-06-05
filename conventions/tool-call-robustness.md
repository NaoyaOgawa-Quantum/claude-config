# Tool call robustness — Claude の tool 呼び出しが「malformed」 で壊れるのを防ぐ

> 適用対象: Claude が **任意の tool call (特に Bash / Edit)** を生成する全ての場面。 hook 作成に限らない。
> hook script を書くときの bash 3.2 parser bug は **別 layer** の話 (= `hook-authoring.md §1` 参照)。

---

## 現象

tool call が `Your tool call was malformed and could not be parsed. Please retry.` で失敗し、 retry も失敗すると `ターンが失敗しました` になる。 これは harness が **Claude の生成した tool call (構造化テキスト) を deserialize できなかった** failure であって、 危険操作の block ではない (= permission dialog / hook deny とは別物)。 実害は通常なし (= tool は実行されず状態は不変) だが、 user を待たせ session が止まる。 「やってはならない操作をした」 と誤解されやすいので、 発生時は **まず「フォーマットが壊れただけで何も実行・破壊していない」 と明示**する。

## トリガー (= 2026-06-05 に 3 回連続再発で同定)

| トリガー | 例 |
|---|---|
| Bash コマンド内の **特殊文字密集** | 多段パイプ + 正規表現 (`grep -oE` で引用符を含むパターン)、 heredoc (`python3 - <<'PY' ... PY`)、 引用符の入れ子 |
| **長い本文 + markdown テーブル + 絵文字** の直後の tool call | パイプ文字を多用した表 + 絵文字を詰めた長文応答の末尾に tool call を置く |

原因: tool call serialization の delimiter / escape と、 コマンド文字列・本文中の特殊文字 (引用符・パイプ・山括弧・改行・heredoc terminator) が干渉し、 生成 token 列の構造整合が途中で崩れる。

## 対策 (= 確立、 以後これに従う)

1. **複雑ロジックは `Write` でファイル化 → 単純コマンドで実行**。 Bash インラインの heredoc / 言語埋め込みは禁止 (= 中間 file に書いて `python3 /tmp/x.py` で呼ぶ)。
2. **Bash インラインは特殊文字を薄く**: パイプ最小、 引用符 1 レベル、 正規表現の引用符ネスト回避。
3. **JSON パース・正規表現・条件判定は Python / script ファイルへ**。 grep / awk ワンライナーで無理に処理しない。
4. **tool call を含むターンは本文をプレーン短文に**。 markdown テーブル・大量絵文字・コードブロックは tool call の無い応答ターンに限定する (= chat-style の装飾は tool-call-free ターン側に寄せる)。
5. **`cd` を compound command に入れない** (= 別途 permission prompt を誘発する)。 `git -C <dir>` 等で代替。
6. **commit message など複数行 + 山括弧 (Co-Authored-By 等) を含むものはファイルに書いて `git commit -F`** で渡す (= `-m "..."` 内の山括弧・改行を避ける)。
7. **生成前の self-check**: 「この tool call は引用符・パイプ・heredoc・山括弧をいくつ含むか? 多ければファイル化」 を 1 回問う。

## メタ規律 (= なぜ 3 回も再発したか)

1 回目の後、 原因を「コマンドが複雑」 と漠然と捉え、 heredoc という **具体パターン** だけ警戒した。 真の不変条件 =「**特殊文字の密度**」 に一般化できず、 2 回目を別形態 (Python 埋め込み) で再発させた。 **具体の表層を潰すのではなく抽象 (特殊文字密度) を抽出する** — 表層モグラ叩きは反復する。 これは規律一般の failure mode で、 CLAUDE.md inline §3「事実主張の前に不確実性を expose するか問う」 と同じ「具体 trigger を抽象 invariant に昇格させる」 構造。

## 限界 (= 誇張しない)

これは Claude の **生成挙動** であり、 規約を書いても「生成時に必ず従う」 保証はなく、 hook での機械 enforcement も (生成前の self-gate なので) 困難 — `hook-authoring.md §5.1` の単一視点 self-reference 不能と同型の問題。 主防御は **実行時の自己規律** (上記 7 点)。 本 file は memory aid であって enforcement ではない、 という前提で読むこと。

## 関連

- `hook-authoring.md §1` — bash 3.2 の `$(...)` + heredoc parser bug。 **別 parser** (= macOS stock bash) だが回避策 (中間 file 化) が共通。
- `hook-authoring.md §5.1` — 単一視点 self-reference の geometric 不能 (= 本 file「限界」 section の理論的根拠)。
- `odakin-prefs/chat-style.md` — 絵文字・装飾の方針 (= 対策 4 で「tool-call-free ターンに寄せる」 と補完関係)。

# secret-handoff: Secret をユーザーの clipboard 経由で安全に運ぶ手順

Token / API key / SSH 鍵 / 各種 credential を Claude がユーザーに `~/.secrets/<name>` 等のローカル配置先へ書き込ませる場面で、**chat に literal を貼らせない原則** (例: `discord-bot.md §「Bot Token の取り扱い」`) と組み合わさったとき、ユーザーは secret を **clipboard 経由で** ブラウザ → ターミナルに運ぶことになる。このときに発生する再現性の高い罠と回避手順。

## The trap: clipboard は 1 個しかない

「ブラウザで secret コピー → Claude が出したコマンドを chat からコピー → ターミナルに貼って Enter」 という流れだと、**Claude のコマンドを clipboard にコピーした時点で secret は消えている**。特に `pbpaste > ~/.secrets/<name>` のように clipboard 内容そのものをファイルに書く方式は完全に破綻する — ファイルには **Claude が提示したコマンド文字列がそのまま書き込まれる**。

判定: ファイル長 ≈ 提示したコマンド長 になっていたら、ほぼ確実にこの罠を踏んでいる。`wc -c` の数字が secret の想定長 (例: Discord Bot Token なら 70-72) でなく、3 桁オーダーの中途半端な値 (160 前後等) になる。

この罠は構造的で、reflex で何度も再発する (2026-05-01、Discord Bot Token を `~/.secrets/<bot>-token` に運ぶ手順で Claude が同セッション内で 2 回連続して `pbpaste` 系を提示してしまい、ファイル内容は両方とも提示コマンド文字列そのものだった)。

## Fix: ターミナル側を先に「stdin 待ち」 状態にする

正しい順序は **「先にターミナルでコマンド受付状態を作る → ブラウザに切り替えて secret コピー → ターミナルに戻って Cmd+V」**。これなら clipboard は 1 回だけ secret 専用に使われ、競合しない。

### パターン A: `cat > file` (シンプル、画面 echo 許容)

```bash
cat > ~/.secrets/<name>
```

→ Enter で stdin 待ちになる (プロンプトが返らないのが正しい状態)。ブラウザに切替えて secret コピー → ターミナルに戻り Cmd+V → Enter (paste の改行) → Ctrl+D で確定。

副作用: paste 時に secret が **画面に echo される** (1 行表示)。物理画面に他人が見えない前提なら許容、共用作業環境では下のパターン B を使う。

### パターン B: `read -rs` (画面に echo されない)

```bash
read -rs SECRET < /dev/tty && printf '%s' "$SECRET" > ~/.secrets/<name> && unset SECRET
```

→ 1 行で stdin 待ちになり、Cmd+V → Enter で完了 (Ctrl+D 不要)。secret は画面に出ない。`unset SECRET` で shell 変数からも消す。

`-r` は backslash escape 無効化、`-s` は echo 抑制。`printf '%s'` は末尾改行を入れないので、`tr -d` 系の trim を後から呼ばなくて済む (curl の `Authorization` header に直接渡せる)。

### permission

書き込み直後に `chmod 600`:

```bash
chmod 600 ~/.secrets/<name>
```

ディレクトリは事前に `mkdir -p ~/.secrets && chmod 700 ~/.secrets`。作成→ chmod の race は single-user macOS の `~/.secrets/` (700) 配下では実害ないが、過敏な環境では `(umask 077; cat > ~/.secrets/<name>)` で atomic にできる。

### 検証は別ブロックで

```bash
wc -c ~/.secrets/<name>
```

これは **必ず別ブロックで提示する**。書き込みコマンドと `&&` で連結すると、ユーザーがその 1 行を clipboard コピーした時点で secret が消える同じ罠を踏ませる。

## Anti-pattern (使ってはいけない)

```bash
pbpaste > ~/.secrets/<name>             # 罠: Claude のこの行をコピーした瞬間に secret が消える
echo "$(pbpaste)" > ~/.secrets/<name>   # 同上
some_cmd "$(pbpaste)"                   # 同上、clipboard を読む全コマンドが該当
```

`pbpaste` (macOS) / `xclip -o` / `wl-paste` (Linux) を **secret 取り込みに使う案を Claude が出した時点で誤り**。Claude のコマンド文字列で clipboard が確実に上書きされている。

## Claude への指示 (How to apply)

Secret を `~/.secrets/<name>` 系に運ぶ手順を提示する時は **必ず stdin-wait 先行 pattern** を使う:

1. 最初に `cat > file` または `read -rs ... < /dev/tty ...` を提示 (= ターミナルを入力待ちに)
2. その上で「ブラウザで secret コピー → Cmd+V → Enter → Ctrl+D」 の順序を文章で明示
3. 検証 (`wc -c`) と permission (`chmod 600`) は **必ず別ブロック**で並べる
4. `pbpaste` を使うコマンド案が頭をよぎったら、それは clipboard 競合の罠 — 即破棄

## なぜ繰り返すのか (構造的バイアス)

「ユーザーが secret を clipboard で運ぶ」 と「Claude がコマンドを clipboard 経由で提示する」 を独立に扱ってしまう reflex。両者が同じ clipboard を競合する事実が見えない。`pbpaste > file` の **見た目の単純さ** が、その内側で `pbpaste` が実行される時点では clipboard が既に汚染されている事実を覆い隠す。

検出経路: 「ユーザーに『これをコピペして実行して』 と提案するコマンドが、その実行結果として clipboard 内容に依存する」 → 矛盾、即破綻。提案前にこの 1 行を自問する。

## 関連

- `discord-bot.md §「Bot Token の取り扱い」` — Token を chat に貼らせない原則 (本ファイルの前提条件)
- `~/Claude/CONVENTIONS.md §5「安全規則」` — secret 全般の git/ chat への流出禁止

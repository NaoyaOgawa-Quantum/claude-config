# macOS Claude.app pty leak workaround

**症状**: 2026-05-15 macOS Ventura 13.7.x で観測。 Claude.app desktop プロセス (= `/Applications/Claude.app/Contents/MacOS/Claude`) が **`kern.tty.ptmx_max` = 511 (= system 上限) の pty を全部独占**し、 新規 Terminal.app / iTerm2 等が `forkpty: Device not configured` (= 「新しいプロセスを作成して擬似 tty を開くことができませんでした。」) で起動不可になる。

これは **Claude.app の pty leak 系 bug** と推察 (= 各 Claude Code session が pty を allocate し、 終了時に release していない蓄積)。 Anthropic 側 fix 待ち候補。

## Diagnosis

```bash
# system 上限と現状確認
sysctl kern.tty.ptmx_max
# → kern.tty.ptmx_max: 511 (= macOS Ventura default)

# 誰が pty を握っているか
lsof 2>/dev/null | grep -cE '/dev/ptmx'
# → 511 (= 上限ぴったり) なら詰まっている

# 詳細: どのプロセスが何個か
lsof 2>/dev/null | awk '/\/dev\/ptmx/ {c[$1" "$2]++} END {for (k in c) print c[k], k}' | sort -rn | head
# → "511 Claude 82547" のような出力なら Claude.app が独占
```

## Workaround: sysctl 段階的拡張

`kern.tty.ptmx_max` は **runtime で write 可能だが、 増加量に kernel 制約**あり (= 1 回 sysctl 呼び出しで current の `~25%` 程度しか上げられない、 ratio で言うと約 1.2 まで)。 一気に 511 → 2048 等は `Invalid argument` で reject される。

### 実測 (2026-05-15 macOS Ventura 13.7.8)

| from | to | delta | ratio | result |
|---|---|---|---|---|
| 511 | 512 | +1 | 1.002 | OK |
| 512 | 514 | +2 | 1.004 | OK |
| 514 | 516 | +2 | 1.004 | OK |
| ... 続けて指数的 +4, +8, +16, +32, +64, +128 ... | | | | OK |
| 640 | 768 | +128 | 1.2 | OK |
| 768 | 896 | +128 | 1.166 | OK |
| 896 | 960 | +64 | 1.071 | OK |
| 960 | 1024 | +64 | 1.067 | **NG (= Invalid argument)** |

**Hard ceiling は ~960-1023 付近**。 1024 以上には上がらない (= kernel-locked)。

### Chain で 1 dialog で実行

`sudo` 経由で password が要るが、 osascript で複数 sysctl 呼び出しを `;` で連結すれば admin dialog は 1 回:

```bash
osascript -e 'do shell script "sysctl kern.tty.ptmx_max=512 ; sysctl kern.tty.ptmx_max=514 ; sysctl kern.tty.ptmx_max=518 ; sysctl kern.tty.ptmx_max=526 ; sysctl kern.tty.ptmx_max=542 ; sysctl kern.tty.ptmx_max=574 ; sysctl kern.tty.ptmx_max=638 ; sysctl kern.tty.ptmx_max=766 ; sysctl kern.tty.ptmx_max=894 ; sysctl kern.tty.ptmx_max=958" with administrator privileges'
```

(= 段階的 2 倍弱で 511 → 958 を 1 dialog で実行。 user は password 1 回入力)

### Reboot で reset、 persistent 化は LaunchDaemon

`sysctl -w` は揮発。 reboot 時に persistent に上限を引き上げたい場合は LaunchDaemon plist で起動時 sysctl を仕掛ける (= `/Library/LaunchDaemons/local.ptmx-bump.plist` 等)。 ただし Apple の SIP / kernel-level 制約で 1024 以上は無理なので、 LaunchDaemon でも `~958` 程度が天井。

### 真の対策: Claude.app restart

pty leak の根本対処は Claude.app を完全 quit して pty を release させること。 ただし現在の Claude Code session が消える (= chat history は Claude desktop 永続化されるので chat 自体は restart 後復元可、 但し model の working memory はリセット)。

restart 方法 (= terminal が開けない状態でも可):
1. **Activity Monitor** を Cmd+Space → 起動
2. 検索バーに `Claude` → CPU タブで filter
3. `/Applications/Claude.app/Contents/MacOS/Claude` プロセスを select
4. 左上「ⓧ Stop」 → 「強制終了」
5. Terminal.app を試す (= 復活確認)
6. Claude.app 再起動 → conversation 再開

## なぜ気づきにくいか

- Claude.app は normal SwiftUI app に見え、 pty leak の症状は **side effect として Terminal が開けない** だけ
- `sysctl kern.tty.ptmx_max` は 511 のまま (= 数字だけ見ても異常見えない)
- `lsof | grep ptmx` で初めて Claude.app が 511 個独占しているのが見える
- ユーザーは「Terminal が壊れた」 と誤認しがち (= Terminal.app の問題ではなく、 system の pty pool が枯渇しているだけ)

## How to apply

- macOS で `forkpty: Device not configured` を見たら、 まず `lsof | grep -cE '/dev/ptmx'` で count を取り、 511 (or 上限) 付近なら pty 枯渇を確認
- どのプロセスが原因か `lsof` 詳細で特定 (= Claude.app が高確率)
- 即時復活させたい場合は段階的 sysctl bump (= chain で 1 dialog 実行)
- 根本対処は犯人プロセス restart
- Claude.app 自身のセッションを失わずに直す必要があれば sysctl bump 一択

## 関連

- Anthropic に bug report 候補 (= pty leak)
- macOS の pty pool 上限は kernel-locked (= 1024 が hard ceiling、 SIP 関連)

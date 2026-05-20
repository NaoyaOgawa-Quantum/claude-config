# Claude Code hooks の作成 + 配信規律

> 適用対象: `claude-config/hooks/` (= layer 1) + 個人層の `<personal-layer>/hooks/` (= layer 3) の hook script 全般。 hook 作成・配信・audit の **3 種類の構造的 trap** を扱う。
>
> 関連 hook: `claude-config/hooks/*.sh` (= 既存 8 hooks)、 hook 配信機構の正本は `claude-config/setup.sh` Step 2 (= `install_hooks()` 関数)

---

## 概論: hook は他の script と質的に異なる category

普通の utility script は:
- (i) 実行環境を作者が選べる (= `#!/usr/bin/env python3` 等で modern runtime を assume 可)
- (ii) 失敗時は exit code + stderr で expose される
- (iii) 1 行で起動できる (= command path 1 個指せば動く)

claude-code hook は **3 つとも逆**:
- (i) **macOS stock `/bin/bash` (= 3.2.57) で起動**。 homebrew bash 5.x で書いて動かしただけでは ship 不可
- (ii) **配信不全は silent**。 symlink broken / settings.json entry 欠落の各 mode で stderr 不在
- (iii) **配信が 2 段** (= filesystem symlink + settings.json 登録) で、 1 段だけ揃っても起動しない

→ hook 作成者は **特殊な category の作業をしている** という認識から始める。 普通の bash convention で十分と思った瞬間に下記 3 trap のどれかを踏む。

---

## §1. bash 3.2 の `$(...)` + heredoc body の quote escape parser bug

### 問題

`$(...)` command substitution 内に heredoc を置き、 heredoc body に literal `"` または `'` (= 例えば Python regex の `[\"']` パターン) を含めると、 bash 3.2 の parser が外側 `$(...)` の閉じ `)` を find する際に body 内の quote を一部 consume、 **遥か後の行 で `syntax error near unexpected token '('`** を報告する。

quoted heredoc 開始 token (`<<'PYEOF'`) は body を no-expansion にする contract のはずだが、 bash 3.2 の `$(...)` parser は **その contract を無視して body を scan する** (= 既知の bash 3.2 限界、 5.x で修正)。

### Reproducer (= 2026-05-20 実遭遇)

```bash
HEREDOC_MSG="$(
  python3 - <<'PYEOF' 2>/dev/null
import re
# このパターン内の \" \' で bash 3.2 が confusion
pat = re.compile(r"<<-?\s*[\"']?([A-Z]+)[\"']?\s*")
PYEOF
)"
```

- `bash` (homebrew 5.x): 通る
- `/bin/bash` (macOS stock 3.2.57): `syntax error near unexpected token '('` を 50〜100 行先で報告

### 回避策

heredoc body 内の literal quote を **hex escape で書き換える**:

```bash
pat = re.compile(r"<<-?\s*[\x22\x27]?([A-Z]+)[\x22\x27]?\s*")
#                          ↑ "          ↑ '
```

`\x22` = `"`、 `\x27` = `'`。 Python (および大半の regex engine) は同 escape を理解するので semantics 不変。 bash 3.2 parser は body 内 quote を見ないので heredoc 終端 (`PYEOF`) で正しく停止できる。

別解: 中間 file に書き出す (= `python3 -c '...'` への移行は引用問題が増えるので非推奨、 heredoc を `>/tmp/script.py` で先に書いて `python3 /tmp/script.py` で呼ぶのは clean だが手数が増える)。

### Debug が困難な理由 / メタ規律

- minimal isolated test (= heredoc 1 個を `$(...)` 無しで実行) は通る → 「block の中身が壊れた」 と reflex 判定しがち。 真因は **block 間 interaction** (= 外側 parser が内側 body を scan する parser bug)
- 「error 報告行」 と「真因行」 が大きく乖離する → 修正対象を誤特定して時間を溶かす

**メタ規律**: hook を書いた直後に `/bin/bash -n <hook>` で syntax check + minimal stdin で 1 回 fire 確認。 homebrew bash で書いて満足しない。 macOS stock bash で fail する書き方を完成形と認識する事故を予防。

---

## §2. hook 配信正常性の 3 軸 audit (= 1 軸欠けて silent malfunction)

### 問題

claude-code が hook を起動するには **3 軸全てが揃う必要**:

| 軸 | 配信先 / 確認方法 | 失敗時の症状 |
|---|---|---|
| (a) **symlink target 健全性** | `~/.claude/hooks/<name>.sh` が存在し target も存在 (= `[ -e <path> ]` が true) | hook spawn 即 fail。 claude-code は exit code を log するが user 通常見ない |
| (b) **settings.json entry** | `~/.claude/settings.json` の `hooks.PreToolUse[]` (または PostToolUse) に該当 command path が登録 | claude-code が hook を invoke しない。 stderr 不在で気付かない |
| (c) **logic 健全性** | realistic JSON stdin で hook 起動 + 期待出力 (= ask JSON / warn 出力 / silent) 確認 | (a)(b) OK でも logic bug で空振り、 false negative |

3 軸全て silent failure mode を持つ。 「symlink 作った」 「settings.json 直した」 「テスト書いた」 のどれか 1 つで「fix 完了」 と claim するのは error。

### 実例 (= 2026-05-20 retroactive 発覚)

| 失敗 mode | 詳細 | 観測された機能停止期間 |
|---|---|---|
| (a) broken symlink | `~/.claude/hooks/google-url-guard.sh -> <non-existent path>` の状態 (= 過去の personal-layer hook 試行残骸、 target dir 不在) | **約 1 ヶ月** (link mtime から逆算)。 この間、 機械的 enforcement layer 不在 → user 規約違反の retroactive audit 対象に |
| (b) settings.json entry 欠落 | `~/.claude/hooks/expensive-tmp-guard.sh` symlink は存在、 但し `settings.json` の PreToolUse list に未登録 | 不明 (= setup.sh 直近実行時に partial 完了した可能性) |
| partial install (= §4 参照) | symlink だけ手動修復 + settings.json は手付かず → (a) 解消、 (b) は残存 | (b) 軸単独の silent malfunction が継続 |

### 防止策 / audit method

**ゲート質問** (= hook 配信を「fix した」 と claim する前):
1. `[ -e ~/.claude/hooks/<name>.sh ]` (= symlink target 健全?)
2. `jq -e --arg c "<name>.sh" '.hooks.PreToolUse[] | select(.hooks[]?.command | contains($c))' ~/.claude/settings.json` (= entry 存在?)
3. realistic JSON stdin で hook 起動 → 期待出力 確認 (= logic 健全?)

3 つとも yes でない限り「動く」 と claim しない。

**audit script の design 推奨**: hook ごとに 3 軸 check して silent malfunction を expose する script を `claude-config/scripts/audit-hooks.sh` 等で実装するのが筋。 dashboard 統合候補。 本 file 作成時点 (= 2026-05-20) では未実装、 個別 hook の本気運用前に 1 度書く価値あり。

**hook 配信 drift の根本因**: setup.sh が periodic 実行されないと、 claude-config に新 hook を commit / 既存 hook の symlink target を変更しても、 各マシンの `~/.claude/hooks/` への配信は遅延する。 対処の候補:
- (i) setup.sh を post-merge git hook で auto-run (= 既存 Step 6 で claude-config 自身の post-merge は導入済、 hook install step もここで毎回 idempotent 再実行する余地)
- (ii) dashboard に 3 軸 audit を組み込み、 drift を session 開始時に surface
- (iii) hook ごとに self-test を持たせ、 hook 自身が起動時に自分の配信状態を log

setup.sh 自体は idempotent design なので (i) は実装コスト低。 但し `git pull` のたびに走るとうるさい場合あり、 trade-off は user 判断。

---

## §3. PreToolUse warn mode 出力の spec uncertainty

### 問題

claude-code hook の PreToolUse phase で **warn** (= block しないが user / Claude に message を surface) を実装するとき、 spec 上 visible になる経路が複数あり version 依存:

| 出力経路 | 仕様確度 | surface 経路 |
|---|---|---|
| **stderr** | 高 (= `permissionDecision: ask` 時の error message 経路として確立) | `ask` / `deny` 時は user 可視。 `allow` (= 通常 flow) 時は spec 不明確 |
| **stdout JSON `hookSpecificOutput.additionalContext`** | 中 (= PostToolUse の system-reminder と類似 model) | 次ターン Claude に inject される (が、 user に直接 surface するかは別) |
| **stdout JSON top-level `systemMessage`** | 低 (= 旧 spec field の可能性、 deprecated 候補) | version 依存、 fallback として残す |

`ask` / `deny` (= block 系) は spec 確立済で stderr が確実に surface する。 warn (= 通すが message 出す) は claude-code 内部の通常 permission flow に乗せるため、 message 経路が spec で明確に定義されていない。

### 実装推奨

warn 用途では **3 経路を defensive に併用** (= どれが surface しても OK):

```bash
# stderr (= log + ask/deny 時の確実経路、 allow 時は best-effort)
printf '%s\n' "$WARN_TEXT" >&2

# stdout JSON: 通常 permission flow + additionalContext で次ターン inject
jq -n --arg msg "$WARN_TEXT" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": $msg
  },
  "systemMessage": $msg
}'

exit 0
```

`permissionDecision` field は **出さない** (= 通常 permission flow に流す = ユーザー設定の auto-allow / ask を override しない)。 `permissionDecision: "allow"` を出すと user の手動許可 flow を bypass する副作用があるので warn 用途では不適切。

### Dry-run 観察事項 (= warn hook 投入後に user に依頼)

warn hook を MVP で投入したら、 一定期間 (= 数週間〜1 ヶ月) 観察して以下を decide:
- どの経路 (stderr / additionalContext / systemMessage) が **実際 surface したか** (= claude-code 当該 version での実 spec)
- false-positive 率 (= 「surface したが実 leak ではない」 の比率)
- escalation (= `permissionDecision: "ask"` 化) の可否

surface しなかった場合: 残り 2 経路に依存している、 または warn hook の effect が user 観察に届いていない、 のどちらか。 後者なら escalation を検討、 前者なら simplify する余地。

---

## §4. Partial install state (= §2 の specific failure mode、 注意喚起)

### 問題

§2 の 3 軸を分離して扱った時の典型 failure mode (= 「一部だけ直した」 が「全部直した」 と誤認):

- 手動 `ln -s` だけ実行 → symlink あり / settings.json entry 不在 = silent malfunction
- setup.sh の途中で fail → 直前まで完了した step は残るが後続 step が skip = partial state
- 個人層 hook (= layer 3) を ad hoc に install → settings.json merge を忘れがち

setup.sh の `install_hooks()` 関数内の **「symlink 配置 → settings.json への jq merge」 dual-step は atomic な 1 unit として扱う** (= 関数内で逐次実行、 該当 logic の正本は `claude-config/setup.sh`)。 これを分離して片方だけ実行すると partial state を produce する。

### 防止策

hook 配信を「fix した」 と claim する前に **§2 の 3 軸ゲート質問を独立に通す**。 「`ln -s` 通った」 「config に書き足した」 のどちらか単独では不十分。

**規律**: hook 配信修復 task では、 必ず symlink + settings.json + try-fire の 3 step を **同じ作業 unit に bundle** する。 分離すると次の作業者 (= 別 session の Claude / 別マシンの自分) が partial state を canonical と誤認する。

---

## 関連

- `claude-config/setup.sh §Step 2 install_hooks()` — 配信機構の正本 (= 3 軸を atomic に扱う reference implementation)
- `claude-config/hooks/*.sh` — 既存 hook 8 個 (= 本 file 作成時点)。 §1 (bash 3.2 trap) の audit 対象
- `conventions/multi-machine-state.md` — 多マシン audit 規律 (本 file と相補、 hook 配信が drift する具体例として cross-reference)
- `docs/personal-layer.md` — layer 3 個人層 hook の配置規律 (= claude-config 側 hook と layer 3 hook の責務分離)

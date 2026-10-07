#!/usr/bin/env bash
# install-claude-app-account-mirror.test.sh — install-claude-app-account-mirror.sh の入れる / 入れ直し / 状態 / 外す と、 account が 1 つの時・macOS 以外で何もしないことの test
#
# launchctl と uname は偽物を PATH の先頭に置く (= 実 launchd に触らず、 Linux CI でも install 経路を通す)。
# desktop app の保存 dir・account・app 本体は一時 dir に偽物を作り、 engine に引数で渡す (本物の registry に触らない)。
#   T1 入れる: plist (見張る dir 2 つ / 5 分 / 60 秒 / --apply --quiet / 偽の保存 dir を指す) + bootstrap
#   T2 入れ直し: bootout してから bootstrap、 plist は同じ
#   T3 --status: 読み込み済み + engine の状態
#   T4 --uninstall: bootout + plist を消す
#   T5 account が 1 つ: 入れない (exit 非 0、 plist 無し)
#   T6 macOS 以外: 何もしない
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/install-claude-app-account-mirror.sh"
command -v python3 >/dev/null 2>&1 || { echo "SKIP: python3 が無い"; exit 0; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "  ok: $1"; }
ng() { FAIL=$((FAIL+1)); echo "  NG: $1"; }

BIN="$TMP/bin"; STATE="$TMP/state"; CALLS="$TMP/calls"
mkdir -p "$BIN" "$STATE"
: > "$CALLS"
printf '#!/bin/sh\necho "${FAKE_UNAME:-Darwin}"\n' > "$BIN/uname"
cat > "$BIN/launchctl" <<EOF
#!/bin/sh
echo "\$*" >> "$CALLS"
case "\$1" in
  bootstrap) : > "$STATE/loaded" ;;
  bootout)   [ -f "$STATE/loaded" ] || exit 3; rm -f "$STATE/loaded" ;;
  print)     [ -f "$STATE/loaded" ] ;;
  *)         exit 1 ;;
esac
EOF
chmod +x "$BIN/uname" "$BIN/launchctl"
if [ "$(PATH="$BIN:$PATH" command -v launchctl)" != "$BIN/launchctl" ]; then
  echo "FAIL: 偽の launchctl が PATH の先頭に来ない (実 launchd に触るので中止)"; exit 1
fi

# 偽の desktop app: account 2 つ (架空の uuid)、 app 本体 (Info.plist + app.asar は engine の selftest と同じ最小形)
H="$TMP/home"; UD="$H/ud"; APP="$TMP/Claude.app"
A=aaaaaaaa-1111-4111-8111-111111111111; B=bbbbbbbb-2222-4222-8222-222222222222
OA=0a0a0a0a-3333-4333-8333-333333333333; OB=0b0b0b0b-4444-4444-8444-444444444444
mkdir -p "$UD/claude-code-sessions/$A/$OA" "$UD/claude-code-sessions/$A/$OB" "$UD/claude-code-sessions/$B/$OB" \
  "$H/.claude-alpha" "$APP/Contents/Resources"
# A は org dir が 2 つ (どちらも session なし) = CLI の login 設定の org で決まる / B は org dir が 1 つ = それに決まる
printf '{"oauthAccount":{"accountUuid":"%s","emailAddress":"alpha@%s","organizationUuid":"%s"}}\n' \
  "$A" "example.invalid" "$OA" > "$H/.claude-alpha/.claude.json"
python3 - "$HERE/claude-app-account-mirror.py" "$APP" <<'PY'
import importlib.util, plistlib, sys
spec = importlib.util.spec_from_file_location("m", sys.argv[1]); m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with open(sys.argv[2] + "/Contents/Info.plist", "wb") as f:
    plistlib.dump({"CFBundleShortVersionString": "9.1.0"}, f)
m._fake_asar(sys.argv[2] + "/Contents/Resources/app.asar", {"index.js": m.GOOD_JS})
PY

LA="$TMP/la"; LOGD="$TMP/logs"; PL="$LA/com.claude-config.account-mirror.plist"
run() {
  PATH="$BIN:$PATH" HOME="$H" ACCOUNT_MIRROR_LA_DIR="$LA" ACCOUNT_MIRROR_LOG_DIR="$LOGD" \
    ACCOUNT_MIRROR_ENGINE_ARGS="--home $H --user-data $UD --app $APP" sh "$SCRIPT" "$@"
}
pl() { python3 -c 'import json,plistlib,sys; print(json.dumps(plistlib.load(open(sys.argv[1],"rb")), sort_keys=True))' "$PL"; }

echo "T1 入れる"
out="$(run 2>&1)"; rc=$?
if [ "$rc" -eq 0 ] && [ -f "$PL" ]; then ok "rc 0 + plist"; else ng "rc=$rc / $out"; fi
j="$(pl 2>/dev/null)"
python3 - "$j" "$UD" <<'PY' && ok "plist の中身" || ng "plist の中身: $j"
import json, sys
d = json.loads(sys.argv[1]); ud = sys.argv[2]
assert d["Label"] == "com.claude-config.account-mirror"
assert sorted(d["WatchPaths"]) == sorted([f"{ud}/claude-code-sessions/aaaaaaaa-1111-4111-8111-111111111111/0a0a0a0a-3333-4333-8333-333333333333",
                                           f"{ud}/claude-code-sessions/bbbbbbbb-2222-4222-8222-222222222222/0b0b0b0b-4444-4444-8444-444444444444"])
assert d["StartInterval"] == 300 and d["ThrottleInterval"] == 60 and d["RunAtLoad"] is True
a = d["ProgramArguments"]
assert a[-2:] == ["--apply", "--quiet"] and a[1].endswith("claude-app-account-mirror.py")
assert "--user-data" in a and a[a.index("--user-data") + 1] == ud
assert d["StandardOutPath"].endswith("/logs/claude-account-mirror.log")
PY
grep -q "^bootstrap gui/" "$CALLS" && ok "bootstrap" || ng "bootstrap が呼ばれない: $(cat "$CALLS")"
echo "$out" | grep -q "入れた" && ok "入れた と出る" || ng "出力: $out"

echo "T2 入れ直し"
before="$(pl)"; : > "$CALLS"
out="$(run 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && [ "$(pl)" = "$before" ] && ok "同じ plist" || ng "rc=$rc"
[ "$(head -1 "$CALLS" | cut -d' ' -f1)" = "bootout" ] && grep -q "^bootstrap" "$CALLS" && ok "bootout → bootstrap" \
  || ng "呼び順: $(cat "$CALLS")"

echo "T3 --status"
out="$(run --status 2>&1)"
echo "$out" | grep -q "読み込み済み" && echo "$out" | grep -q "app の点検: Claude 9.1.0 → ok" && ok "状態" || ng "状態: $out"

echo "T4 --uninstall"
: > "$CALLS"
out="$(run --uninstall 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && [ ! -f "$PL" ] && grep -q "^bootout" "$CALLS" && ok "外す" || ng "rc=$rc / $out"
out="$(run --status 2>&1)"
echo "$out" | grep -q "未導入" && ok "外した後の状態 = 未導入" || ng "状態: $out"

echo "T5 account が 1 つ"
rm -rf "$UD/claude-code-sessions/$B"
out="$(run 2>&1)"; rc=$?
[ "$rc" -ne 0 ] && [ ! -f "$PL" ] && ok "入れない" || ng "rc=$rc / $out"

echo "T6 macOS 以外"
out="$(FAKE_UNAME=Linux run 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && echo "$out" | grep -q "macOS 専用" && [ ! -f "$PL" ] && ok "何もしない" || ng "rc=$rc / $out"

echo "install-claude-app-account-mirror.test.sh: $PASS ok, $FAIL fail"
[ "$FAIL" -eq 0 ]

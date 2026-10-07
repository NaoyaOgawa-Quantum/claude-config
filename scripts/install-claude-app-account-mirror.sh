#!/bin/sh
# install-claude-app-account-mirror.sh — desktop の session 一覧の写し (claude-app-account-mirror.py) を launchd に常駐させる / 状態を見る / 外す (macOS、 本人が terminal で実行する)
#
# 使い方:
#   install-claude-app-account-mirror.sh               入れる (plist を書いて読み込む。 何度でも = 入れ直し)
#   install-claude-app-account-mirror.sh --status      常駐・直近の実行・app の点検・台帳・log の末尾
#   install-claude-app-account-mirror.sh --uninstall   外す (写しは残る。 未開封の写しも消すなら先に engine の --undo --apply)
#   install-claude-app-account-mirror.sh --print-plist 書く plist を出すだけ
#
# 動き: launchd job com.claude-config.account-mirror が engine を `--apply --quiet` で回す。 起動の契機 =
#   各 account の session dir の変化 (WatchPaths) + 5 分ごとの保険 (StartInterval 300)、 最短間隔 60 秒
#   (ThrottleInterval)。 読み込んだ直後にも 1 回 (RunAtLoad)。 log = ~/Library/Logs/claude-account-mirror.log
#   (変化が無い回は何も書かない)。 plist の中身の正本 = engine の plist_dict()。
#   止める = touch ~/.claude/account-mirror.off (job は残り、 何もしない)。 規約 =
#   conventions/multi-account-machine-surface.md#session-list-per-account
#
# ⚠️ Claude (auto mode) からは実行しない: classifier が「session 記録の改ざん」 として止める (実測)。 本人が貼る。
#
# env (test 用): ACCOUNT_MIRROR_LA_DIR / ACCOUNT_MIRROR_LOG_DIR / PYTHON (launchd から起動する python) /
#   ACCOUNT_MIRROR_ENGINE_ARGS (engine に足す引数。 空白を含む値は渡せない)
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
ENGINE="$HERE/claude-app-account-mirror.py"
LABEL="com.claude-config.account-mirror"
LA_DIR="${ACCOUNT_MIRROR_LA_DIR:-$HOME/Library/LaunchAgents}"
LOG_DIR="${ACCOUNT_MIRROR_LOG_DIR:-$HOME/Library/Logs}"
LOG="$LOG_DIR/claude-account-mirror.log"
PLIST="$LA_DIR/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "macOS 専用 (launchd) = 何もしない"
  exit 0
fi

# launchd は PATH が狭いので python は実体の絶対 path で焼く (/usr/bin/python3 の shim を避ける)
PY="${PYTHON:-}"
[ -n "$PY" ] || PY=$(python3 -c 'import sys; print(sys.executable)' 2>/dev/null)
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  echo "python3 が見つからない"
  exit 1
fi

# shellcheck disable=SC2086
eng() { "$PY" "$ENGINE" ${ACCOUNT_MIRROR_ENGINE_ARGS:-} --launch-agents-dir "$LA_DIR" "$@"; }

loaded() { launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; }

case "${1:-install}" in
  install|--install)
    n=$(eng --watch-paths | grep -c .)
    if [ "$n" -lt 2 ]; then
      echo "desktop app の account が ${n} 個しか無い = 写す先が無いので入れない"
      exit 1
    fi
    if ! eng --app-check; then
      echo "⚠️ この版の app には写しの前提が見つからない = 入れても写さない (版が変われば自動で点検し直す)"
    fi
    mkdir -p "$LA_DIR" "$LOG_DIR" || exit 1
    tmp="$PLIST.tmp.$$"
    if ! eng --print-plist --python "$PY" --log "$LOG" > "$tmp"; then
      rm -f "$tmp"
      echo "plist を作れない"
      exit 1
    fi
    mv "$tmp" "$PLIST"
    launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1
    if ! launchctl bootstrap "$DOMAIN" "$PLIST"; then
      echo "launchctl bootstrap に失敗 ($PLIST)"
      exit 1
    fi
    echo "入れた: $LABEL (見張る session dir ${n} 個 / 5 分ごと / 最短 60 秒)。 最初の実行は今 (log = $LOG)"
    if [ -e "$HOME/.claude/account-mirror.off" ]; then
      echo "⚠️ 止めるスイッチがある = 何も写さない。 再開 = rm ~/.claude/account-mirror.off"
    fi
    echo "状態 = bash $0 --status"
    ;;
  --status)
    if [ -f "$PLIST" ]; then
      if loaded; then echo "launchd: 読み込み済み ($LABEL)"; else echo "launchd: plist はあるが読み込まれていない = bash $0 で入れ直す"; fi
    else
      echo "launchd: 未導入 = bash $0"
    fi
    eng --status
    if [ -f "$LOG" ]; then
      echo "log の末尾 ($LOG):"
      tail -n 8 "$LOG" | sed 's/^/  /'
    fi
    ;;
  --uninstall)
    launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1
    rm -f "$PLIST"
    echo "外した: ${LABEL}。 今ある写しは残る (未開封の写しも消すなら: $PY $ENGINE --undo --apply)"
    ;;
  --print-plist)
    eng --print-plist --python "$PY" --log "$LOG"
    ;;
  -h|--help)
    sed -n '2,20p' "$0"
    ;;
  *)
    echo "不明な引数: $1 (--status / --uninstall / --print-plist)"
    exit 2
    ;;
esac

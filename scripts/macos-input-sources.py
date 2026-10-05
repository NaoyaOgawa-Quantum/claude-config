#!/usr/bin/env python3
"""macOS の入力ソース (キーボード配列・IME とそのモード) を CLI で一覧・有効化・無効化・選択する
(conventions/macos-ime-ascii-layout.md#cli-input-source-switch)。

Text Input Sources (TIS) API を ctypes で呼ぶ (標準 library だけ、 compile 不要、 権限不要)。
変更のあとは別 process で読み直し、 効いたかを確かめて出す (TIS の読みは process の中で古くなる = 同 doc §2 の 5)。
第三者の IME (例: Google 日本語入力) は、 外部 process からの無効化が status 0 を返しても外れない (実測) =
そのときは「効いていない」 と出して終了値 1、 外し方 (システム設定) を示す。

Usage:
  python3 scripts/macos-input-sources.py list [<id の一部>]     # en=有効 / sel=選択中 / cap=選択できる
  python3 scripts/macos-input-sources.py enable  <input source id>
  python3 scripts/macos-input-sources.py disable <input source id>
  python3 scripts/macos-input-sources.py select  <input source id>
  python3 scripts/macos-input-sources.py --selftest

例 = Apple の日本語入力 (ローマ字入力) に切り替える (IME 本体 → ひらがなモード → 選択の順):
  enable com.apple.inputmethod.Kotoeri.RomajiTyping
  enable com.apple.inputmethod.Kotoeri.RomajiTyping.Japanese
  select com.apple.inputmethod.Kotoeri.RomajiTyping.Japanese

終了値: 0 = 効いた (list は常に 0) / 1 = 呼び出しは成功を返したが別 process で読むと効いていない / 2 = 使い方の誤り・id が無い・macOS でない。
"""
from __future__ import annotations

import ctypes
import json
import platform
import subprocess
import sys
import time

_UTF8 = 0x08000100  # kCFStringEncodingUTF8
_cf = _hi = None


def _load():
    global _cf, _hi
    if _cf is not None:
        return
    _cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    _hi = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
    vp = ctypes.c_void_p
    for name, res, args in (
        ("CFArrayGetCount", ctypes.c_long, [vp]),
        ("CFArrayGetValueAtIndex", vp, [vp, ctypes.c_long]),
        ("CFGetTypeID", ctypes.c_ulong, [vp]),
        ("CFStringGetTypeID", ctypes.c_ulong, []),
        ("CFBooleanGetTypeID", ctypes.c_ulong, []),
        ("CFStringGetCString", ctypes.c_bool, [vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]),
        ("CFBooleanGetValue", ctypes.c_bool, [vp]),
        ("CFRelease", None, [vp]),
    ):
        f = getattr(_cf, name)
        f.restype, f.argtypes = res, args
    for name, res, args in (
        ("TISCreateInputSourceList", vp, [vp, ctypes.c_bool]),
        ("TISGetInputSourceProperty", vp, [vp, vp]),
        ("TISEnableInputSource", ctypes.c_int32, [vp]),
        ("TISDisableInputSource", ctypes.c_int32, [vp]),
        ("TISSelectInputSource", ctypes.c_int32, [vp]),
    ):
        f = getattr(_hi, name)
        f.restype, f.argtypes = res, args


def _key(name: str):
    return ctypes.c_void_p.in_dll(_hi, name).value


def _prop(src, key_name: str):
    ref = _hi.TISGetInputSourceProperty(src, _key(key_name))
    if not ref:
        return None
    tid = _cf.CFGetTypeID(ref)
    if tid == _cf.CFStringGetTypeID():
        buf = ctypes.create_string_buffer(1024)
        return buf.value.decode("utf-8") if _cf.CFStringGetCString(ref, buf, 1024, _UTF8) else None
    if tid == _cf.CFBooleanGetTypeID():
        return bool(_cf.CFBooleanGetValue(ref))
    return None


def _sources():
    """(source ref, info) の list と、 解放する配列を返す (呼び元が CFRelease)。"""
    _load()
    arr = _hi.TISCreateInputSourceList(None, True)
    out = []
    for i in range(_cf.CFArrayGetCount(arr)):
        s = _cf.CFArrayGetValueAtIndex(arr, i)
        out.append((s, {
            "id": _prop(s, "kTISPropertyInputSourceID") or "",
            "name": _prop(s, "kTISPropertyLocalizedName") or "",
            "en": bool(_prop(s, "kTISPropertyInputSourceIsEnabled")),
            "sel": bool(_prop(s, "kTISPropertyInputSourceIsSelected")),
            "cap": bool(_prop(s, "kTISPropertyInputSourceIsSelectCapable")),
        }))
    return out, arr


def _fresh_state(source_id: str):
    """別 process で読み直す (この process の TIS の読みは古いことがある)。"""
    r = subprocess.run([sys.executable, __file__, "_state", source_id], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def cmd_list(pattern: str) -> int:
    rows, arr = _sources()
    for _, info in rows:
        if pattern and pattern not in info["id"]:
            continue
        print(f"{info['id']} | en={int(info['en'])} sel={int(info['sel'])} cap={int(info['cap'])} | {info['name']}")
    _cf.CFRelease(arr)
    return 0


def cmd_change(action: str, source_id: str) -> int:
    rows, arr = _sources()
    hit = [s for s, info in rows if info["id"] == source_id]
    if not hit:
        _cf.CFRelease(arr)
        print(f"id が無い: {source_id} (list で確かめる)", file=sys.stderr)
        return 2
    fn = {"enable": _hi.TISEnableInputSource, "disable": _hi.TISDisableInputSource,
          "select": _hi.TISSelectInputSource}[action]
    status = fn(hit[0])
    _cf.CFRelease(arr)
    time.sleep(0.5)
    st = _fresh_state(source_id) or {}
    want = {"enable": ("en", True), "disable": ("en", False), "select": ("sel", True)}[action]
    ok = status == 0 and st.get(want[0]) is want[1]
    print(f"{action} {source_id}: status={status} → 読み直し en={st.get('en')} sel={st.get('sel')}"
          f" {'= 効いた' if ok else '= ⚠️ 効いていない'}")
    if not ok and action == "disable" and not source_id.startswith("com.apple."):
        print("  第三者の IME は外部 process から外せない (status 0 でも残る、 実測)。"
              " システム設定 → キーボード → 入力ソース「編集…」 で選んで「−」。", file=sys.stderr)
    return 0 if ok else 1


def selftest() -> int:
    if platform.system() != "Darwin":
        print("selftest: macOS でないので skip")
        return 0
    rows, arr = _sources()
    infos = [i for _, i in rows]
    _cf.CFRelease(arr)
    assert infos, "入力ソースが 1 つも読めない"
    assert all(i["id"] for i in infos), "id の読めない入力ソースがある"
    selected = [i for i in infos if i["sel"]]
    assert selected, "選択中の入力ソースが無い"
    st = _fresh_state(selected[0]["id"])
    assert st and st["sel"] is True, f"別 process の読み直しが選択中を返さない: {st}"
    print(f"selftest: ok ({len(infos)} sources, 選択中 = {selected[0]['id']})")
    return 0


def main(argv) -> int:
    if argv[:1] == ["--selftest"]:
        return selftest()
    if platform.system() != "Darwin":
        print("macOS 専用", file=sys.stderr)
        return 2
    if argv[:1] == ["_state"] and len(argv) == 2:
        rows, arr = _sources()
        info = next((i for _, i in rows if i["id"] == argv[1]), None)
        _cf.CFRelease(arr)
        print(json.dumps({"en": info["en"], "sel": info["sel"]} if info else {}))
        return 0
    if not argv or argv[0] == "list":
        return cmd_list(argv[1] if len(argv) > 1 else "")
    if argv[0] in ("enable", "disable", "select") and len(argv) == 2:
        return cmd_change(argv[0], argv[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""page-screenshot.py — web ページ全体を、 スマホや PC の画面幅で 1 枚 (か縦に分けた数枚) の PNG に撮る。 --selftest 内蔵。

Why: 手元の preview を相手が見られない (スマホから会話している等) ときは、 撮った画像を送るしかない。
headless Chrome の `--screenshot` には 3 つの罠がある (実測、 conventions/web-tools.md#headless-page-screenshot):
  - `--window-size` の幅には下限があり、 390 のようなスマホ幅を渡しても広い画面で描かれ、 右が切れた絵になる
  - 別オリジンの iframe (埋め込みプレーヤー・Turnstile) があるページで、 撮った後に Chrome が終わらないことがある
  - ページ全体を `captureBeyondViewport` で撮ると、 別オリジンの iframe が白く写る
そこで Chrome を DevTools の口 (CDP) で動かし、 端末の画面サイズを指定して描かせ、 画面の高さをページ全体に
広げてから撮る。 WebSocket は標準ライブラリだけで話す (Python 3.9 以上、 外部 package なし)。

usage:
  page-screenshot.py <URL> --out <file.png> [--width 390] [--mobile] [--wait 7] [--split 2400] [--chrome PATH]
  page-screenshot.py --selftest

  --width   画面の幅 (CSS px)。 スマホ = 390 (+ --mobile)、 PC = 1280
  --mobile  スマホとして描かせる (viewport の meta・タッチ)
  --wait    読み込み後に待つ秒数 (埋め込みの iframe の描画待ち)
  --split   この高さ (CSS px) ごとに縦に分けて <out>-1.png, <out>-2.png … に書く。 縦に極端に長い画像は
            チャットの添付で届かないことがある (実測: 780×12400 px で送れず、 780×5000 px は届いた)
  URL は http(s):// と file:// のどちらでもよい (生成した HTML を server なしで撮れる)。
  画像の大きさ = 幅 × 高さ × 2 (device pixel ratio 2 で描く)。

出力: 書いた file ごとに 1 行 `<path>\t<幅>x<高さ> (CSS px)`。
制約: Chrome (または Chromium 系) が要る。 既定の場所に無ければ --chrome で渡す。 Chrome との通信が 60 秒止まったら打ち切る。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]
TIMEOUT = 60


# ---------------------------------------------------------------- WebSocket (RFC 6455、 client 側の最小限)
def ws_frame(payload: bytes, opcode: int = 1, mask: bytes | None = None) -> bytes:
    """client → server の frame (client は必ず mask する)。"""
    mask = mask if mask is not None else os.urandom(4)
    n = len(payload)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 65536:
        head += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", n)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def ws_parse(read) -> tuple[int, bytes, bool]:
    """read(n) から frame を 1 つ読む → (opcode, payload, fin)。 server → client は mask されない (されていても外す)。"""
    b1, b2 = read(2)
    fin, opcode = bool(b1 & 0x80), b1 & 0x0F
    masked, n = bool(b2 & 0x80), b2 & 0x7F
    if n == 126:
        n = struct.unpack(">H", read(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", read(8))[0]
    mask = read(4) if masked else None
    data = read(n)
    if mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data, fin


class CDP:
    def __init__(self, ws_url: str):
        u = urlparse(ws_url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=TIMEOUT)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                raise RuntimeError("WebSocket の握手が途中で切れた")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket の握手に失敗: {head[:120]!r}")
        self.next_id = 0

    def _read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("WebSocket が切れた")
            buf += chunk
        return buf

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        mid = self.next_id
        self.sock.sendall(ws_frame(json.dumps({"id": mid, "method": method, "params": params}).encode()))
        while True:   # event (Page.* 等) は読み捨て、 自分の id の返事を待つ
            opcode, data, fin = ws_parse(self._read)
            while not fin:
                _, more, fin = ws_parse(self._read)
                data += more
            if opcode != 1:
                continue
            msg = json.loads(data)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def evaluate(self, expr: str):
        return self.call("Runtime.evaluate", expression=expr, returnByValue=True).get("result", {}).get("value")


# ---------------------------------------------------------------- Chrome
def find_chrome(given: str | None) -> str:
    for c in ([given] if given else []) + CHROME_CANDIDATES + [shutil.which("google-chrome") or "", shutil.which("chromium") or ""]:
        if c and Path(c).exists():
            return c
    raise SystemExit("Chrome が見つからない (--chrome で場所を渡す)")


def open_page(chrome: str, profile: str) -> tuple[subprocess.Popen, str]:
    proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                             "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port_file = Path(profile) / "DevToolsActivePort"   # port 0 = Chrome が空きを選んでここに書く
    deadline = time.time() + 20
    while time.time() < deadline:
        if port_file.exists() and port_file.read_text().strip():
            port = port_file.read_text().split()[0]
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
                page = next(p for p in pages if p.get("type") == "page")
                return proc, page["webSocketDebuggerUrl"]
            except Exception:
                pass
        time.sleep(0.2)
    proc.kill()
    raise SystemExit("Chrome の DevTools の口が開かなかった")


def shoot(url: str, out: Path, width: int, mobile: bool, wait: float, split: int | None, chrome: str) -> list[tuple[Path, int, int]]:
    profile = tempfile.mkdtemp(prefix="page-screenshot-")
    proc, ws_url = open_page(chrome, profile)
    try:
        cdp = CDP(ws_url)
        cdp.call("Page.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", width=width, height=844 if mobile else 900,
                 deviceScaleFactor=2, mobile=mobile)
        if mobile:
            cdp.call("Emulation.setTouchEmulationEnabled", enabled=True)
        nav = cdp.call("Page.navigate", url=url)
        if nav.get("errorText"):   # 開けなかったページ (file が無い・名前が引けない) を撮って成功にしない
            raise SystemExit(f"ページを開けなかった: {nav['errorText']} ({url})")
        time.sleep(wait)
        cdp.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")   # 遅延読み込みを起こす
        time.sleep(2.5)
        cdp.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.8)
        height = int(cdp.evaluate("document.documentElement.scrollHeight") or 0)
        # 画面の高さをページ全体にしてから撮る (captureBeyondViewport では別オリジンの iframe が白く写る)
        cdp.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2, mobile=mobile)
        time.sleep(4)
        step = split or height
        written = []
        for i, top in enumerate(range(0, height, step), start=1):
            h = min(step, height - top)
            shot = cdp.call("Page.captureScreenshot", format="png",
                            clip={"x": 0, "y": top, "width": width, "height": h, "scale": 1})
            path = out if not split else out.with_name(f"{out.stem}-{i}{out.suffix}")
            path.write_bytes(base64.b64decode(shot["data"]))
            written.append((path, width, h))
        return written
    finally:
        proc.kill()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    for n in (0, 5, 125, 126, 300, 65535, 65536, 70000):   # 長さの 3 つの書き方の境目
        payload = bytes(i % 251 for i in range(n))
        frame = ws_frame(payload, mask=b"\x01\x02\x03\x04")
        # client の frame を server が読む形で戻す (mask を外す)
        pos = 0

        def read(k, frame=frame):
            nonlocal pos
            chunk = frame[pos:pos + k]
            pos += k
            return chunk
        opcode, data, fin = ws_parse(read)
        assert (opcode, data, fin) == (1, payload, True), n
    # server → client (mask なし、 2 つに分かれた frame)
    unmasked = bytes([0x01, 3]) + b"abc" + bytes([0x80, 2]) + b"de"
    pos = 0

    def read2(k):
        nonlocal pos
        chunk = unmasked[pos:pos + k]
        pos += k
        return chunk
    o1, d1, f1 = ws_parse(read2)
    o2, d2, f2 = ws_parse(read2)
    assert (o1, d1, f1, o2, d2, f2) == (1, b"abc", False, 0, b"de", True)
    print("✅ selftest PASS (frame の長さ 0〜70000 の往復 / mask あり・なし / 分かれた frame)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--mobile", action="store_true")
    ap.add_argument("--wait", type=float, default=7)
    ap.add_argument("--split", type=int)
    ap.add_argument("--chrome")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.url or not a.out:
        ap.error("URL と --out が要る")
    socket.setdefaulttimeout(TIMEOUT)
    for path, w, h in shoot(a.url, Path(a.out), a.width, a.mobile, a.wait, a.split, find_chrome(a.chrome)):
        print(f"{path}\t{w}x{h} (CSS px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

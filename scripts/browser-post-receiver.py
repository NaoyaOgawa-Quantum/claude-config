#!/usr/bin/env python3
"""browser-post-receiver.py — browser の page が POST した本文を 1 回だけ受けて file に書く (127.0.0.1)

用途: browser の page で作った大きな値 (画素の probe を何十本も、 表の dump) を Python 側で検査したいとき、
`javascript_tool` の戻り値で返すと、 その値がまるごと会話の context に入る (数百 KB で context を食う)。
page から localhost のこの受け口へ POST すれば、 値は file にだけ落ち、 context には件数だけが残る。
小さな値・すでに返してしまった値は transcript から取り出す (scripts/transcript-tool-result.py)。
手順 = conventions/preview.md#tool-result-to-file

使い方:
  browser-post-receiver.py OUT_FILE [--port 8802] [--timeout 300]
    1 件受けたら書いて終わる (Bash の background で起動してから page 側で送る)。
    page 側 (javascript_tool):
      await fetch("http://127.0.0.1:8802/", {method: "POST", mode: "no-cors",
                  headers: {"Content-Type": "text/plain"}, body: JSON.stringify(data)});
    text/plain + no-cors は preflight を起こさない (page の origin が localhost の別 port でも、
    公開 site でも届く)。 待ち受けは 127.0.0.1 だけ = 外から届かない。
  browser-post-receiver.py --selftest
"""
from __future__ import annotations

import argparse
import http.server
import os
import sys
import tempfile
import threading
import urllib.request


def make_handler(out_path: str, done: threading.Event):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            tmp = out_path + ".part"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, out_path)
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            print(f"saved {n} bytes -> {out_path}", flush=True)
            done.set()

        def do_OPTIONS(self):          # preflight, if a caller sends non-simple headers
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, *args):
            pass
    return Handler


def receive_once(out_path: str, port: int, timeout: float) -> int:
    done = threading.Event()
    server = http.server.HTTPServer(("127.0.0.1", port), make_handler(out_path, done))
    server.timeout = 0.5
    deadline = timeout
    while not done.is_set() and deadline > 0:
        server.handle_request()
        deadline -= server.timeout
    server.server_close()
    if not done.is_set():
        print(f"timeout: nothing received on 127.0.0.1:{port} in {timeout:g} s", file=sys.stderr)
        return 1
    return 0


def _selftest() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "probe.json")
        port = 18802
        th = threading.Thread(target=receive_once, args=(out, port, 10.0))
        th.start()
        payload = b'{"probes": [1, 2, 3]}'
        status = None
        for _ in range(50):
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/", data=payload,
                                             headers={"Content-Type": "text/plain"})
                with urllib.request.urlopen(req) as r:
                    status = r.status
                break
            except OSError:
                threading.Event().wait(0.1)
        th.join(15)
        got = open(out, "rb").read() if os.path.exists(out) else None
        for name, cond in (("POST answered 204", status == 204),
                           ("body written verbatim", got == payload),
                           ("server stopped after one request", not th.is_alive())):
            print(f"  [{'ok' if cond else 'FAIL'}] {name}")
            ok = ok and cond
    print("selftest:", "ALL PASS" if ok else "FAILURES above")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--port", type=int, default=8802)
    ap.add_argument("--timeout", type=float, default=300.0)
    a = ap.parse_args()
    return receive_once(a.out, a.port, a.timeout)


if __name__ == "__main__":
    sys.exit(main())

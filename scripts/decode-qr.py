#!/usr/bin/env python3
"""decode-qr.py — Decode QR payloads from screenshots without opening them.

Needs OpenCV (opencv-python) + NumPy. If the interpreter that runs this script
cannot import them, it looks for another python3 on PATH (and /usr/bin/python3)
that can, and re-runs itself with that one once (the python3 first on PATH is
not always the one with the packages; observed).

A QR that is found but cannot be decoded is reported separately from "no QR":
a dense QR photographed as part of a whole page gets too few pixels per module
(observed: detected, not decodable, even after upscaling and thresholding).
Crop from the original file, or photograph the QR alone, close up.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def load_cv() -> tuple[Any, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV and NumPy are required (Python packages: opencv-python, numpy)"
        ) from exc
    return cv2, np


REEXEC_ENV = "DECODE_QR_REEXEC"


def find_cv_python() -> str | None:
    """Another python3 (PATH order, then /usr/bin/python3) that can import cv2 + numpy."""
    seen = {os.path.realpath(sys.executable)}
    candidates = [
        os.path.join(d, "python3") for d in os.environ.get("PATH", "").split(os.pathsep) if d
    ]
    candidates.append("/usr/bin/python3")
    for cand in candidates:
        if not os.access(cand, os.X_OK):
            continue
        real = os.path.realpath(cand)
        if real in seen:
            continue
        seen.add(real)
        try:
            probe = subprocess.run(
                [cand, "-c", "import cv2, numpy"], capture_output=True, timeout=60
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return cand
    return None


def read_image(path: Path, cv2: Any, np: Any) -> Any:
    try:
        raw = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        raise ValueError(f"cannot read image: {exc}") from exc
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("not a readable image")
    return image


def decode_image(image: Any, cv2: Any) -> list[str]:
    detector = cv2.QRCodeDetector()
    values: list[str] = []

    try:
        ok, decoded, _points, _straight = detector.detectAndDecodeMulti(image)
    except (AttributeError, cv2.error):
        ok, decoded = False, ()
    if ok:
        values.extend(value for value in decoded if value)

    if not values:
        value, _points, _straight = detector.detectAndDecode(image)
        if value:
            values.append(value)

    return list(dict.fromkeys(values))


def variants(image: Any, cv2: Any) -> list[Any]:
    """Grayscale, then Otsu-thresholded at 2x: a photographed QR is often only found there."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    big = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    otsu = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return [gray, otsu]


def failure_reason(image: Any, cv2: Any) -> str:
    found = False
    for candidate in [image, *variants(image, cv2)]:
        try:
            found, _points = cv2.QRCodeDetector().detect(candidate)
        except cv2.error:
            found = False
        if found:
            break
    if found:
        return (
            "QR detected but not decodable (too few pixels per module?) "
            "- crop it from the original file, or photograph the QR alone, close up"
        )
    return "no decodable QR code found (if the QR is a small part of the image, crop it first)"


def decode_paths(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    cv2, np = load_cv()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        try:
            image = read_image(path, cv2, np)
            values = decode_image(image, cv2)
            for candidate in variants(image, cv2) if not values else []:
                values = decode_image(candidate, cv2)
                if values:
                    break
            if not values:
                raise ValueError(failure_reason(image, cv2))
            results.append({"source": str(path), "payloads": values})
        except (OSError, ValueError, cv2.error) as exc:
            errors.append(f"{path}: {exc}")
    return results, errors


def selftest() -> int:
    try:
        cv2, _np = load_cv()
    except RuntimeError as exc:
        print(f"SKIP decode-qr.py selftest: {exc}")
        return 0

    payload = "https://example.invalid/prototype-feedback"
    encoder = cv2.QRCodeEncoder_create()
    qr = encoder.encode(payload)
    image = cv2.copyMakeBorder(qr, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
    image = cv2.resize(image, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    assert decode_image(image, cv2) == [payload]
    blank = _np.full((200, 200), 255, dtype=_np.uint8)
    assert failure_reason(blank, cv2).startswith("no decodable QR code found")
    damaged = image.copy()
    h, w = damaged.shape[:2]
    damaged[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3] = 255  # finder patterns stay, data gone
    assert not decode_image(damaged, cv2)
    assert failure_reason(damaged, cv2).startswith("QR detected but not decodable")
    print("decode-qr.py selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decode QR payloads from local images. Payloads are printed, never opened."
    )
    parser.add_argument("images", nargs="*", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    try:
        load_cv()
    except RuntimeError:
        alt = None if os.environ.get(REEXEC_ENV) else find_cv_python()
        if alt:
            print(
                f"(decode-qr: {sys.executable} cannot import OpenCV; re-running with {alt})",
                file=sys.stderr,
            )
            env = dict(os.environ, **{REEXEC_ENV: "1"})
            os.execve(alt, [alt, os.path.abspath(__file__), *sys.argv[1:]], env)

    if args.selftest:
        return selftest()
    if not args.images:
        parser.error("at least one image is required")

    try:
        results, errors = decode_paths(args.images)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            for payload in result["payloads"]:
                print(payload)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

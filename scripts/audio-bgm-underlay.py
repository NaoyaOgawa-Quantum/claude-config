#!/usr/bin/env python3
"""audio-bgm-underlay.py — 仕上がった配信音声 (ジングル + 本編 + ジングル) の本編の下に BGM を敷いた試作を作る (ffmpeg の入口)。

何をするか:
    1. BGM の integrated loudness (ITU-R BS.1770) を測り、 --bgm-lufs (既定 -40) になる利得を決める
    2. BGM を --start から --end まで敷く (足りなければ頭から繰り返す = seamless loop 素材を想定)、
       頭を --fade-in 秒、 尾を --fade-out 秒でフェード
    3. 配信音声に足し算で重ねる (amix は normalize=0 = 入力数で割らない) → 同じ sample rate・channel で書き出す
    4. 出力の loudness / true peak を測って表示する (配信の基準の中かは呼び出し側が判断)

いつ使うか = 「BGM を敷いたらどう聞こえるか」 を共演者・本人に聞かせる試作。 **本採用の仕上げには使わない**
(仕上がった MP3 をもう 1 回符号化する = 2 世代目。 採用が決まったら仕上げ script 〔audio-finish-episode.py〕 に BGM の段を足し、
本編の生の素材から 1 回の符号化で作る)。 考え方の正本 = conventions/podcast-audio-finishing.md#bgm-under-speech。

--start / --end の決め方 (仕上げ script の .json から):
    start = 冒頭ジングルの長さ (intro_jingle_s)              … ジングルの上には乗せない
    end   = 冒頭 + 本編の長さ − 締めの重ね (outro_overlap_s) … 締めのジングルが重なり始める所で消える
    本編の長さ = Part の長さ − trim_head_s − trim_tail_s

使い方:
    python3 audio-bgm-underlay.py <episode.mp3> <bgm.flac> --start 9.86 --end 1993.33 --out <試作.mp3>
    python3 audio-bgm-underlay.py <episode> <bgm> --start … --end … --bgm-lufs -36 --bitrate 96k --out …
    python3 audio-bgm-underlay.py --selftest        # 合成音で 1 本作り、 長さと BGM 区間の音量を確かめる (数秒)

依存 = ffmpeg (libmp3lame、 ebur128 filter)。 標準 library だけ。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def measure(path: str, start: float | None = None, end: float | None = None) -> dict:
    """integrated loudness / true peak を ebur128 で測る。 start/end を渡すとその区間だけ (ファイルの頭から読んで切る)。"""
    af = []
    if start is not None or end is not None:
        s = 0.0 if start is None else start
        trim = f"atrim=start={s}" + (f":end={end}" if end is not None else "") + ",asetpts=PTS-STARTPTS"
        af.append(trim)
    af.append("ebur128=peak=true")
    r = run(["ffmpeg", "-nostats", "-i", path, "-af", ",".join(af), "-f", "null", "-"])
    text = r.stderr
    m_i = re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", text.rsplit("Summary", 1)[-1])
    m_tp = re.search(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", text.rsplit("Summary", 1)[-1])
    if not m_i:
        raise SystemExit(f"ebur128 の結果が読めない: {path}\n{text[-800:]}")
    return {"I": float(m_i.group(1)) if m_i.group(1) != "-inf" else -math.inf,
            "TP": float(m_tp.group(1)) if m_tp and m_tp.group(1) != "-inf" else None}


def duration(path: str) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path])
    return float(json.loads(r.stdout)["format"]["duration"])


def underlay(episode: str, bgm: str, start: float, end: float, out: str, bgm_lufs: float,
             fade_in: float, fade_out: float, bitrate: str, title: str | None) -> dict:
    if end <= start:
        raise SystemExit(f"--end ({end}) は --start ({start}) より後")
    ep_len = duration(episode)
    if end > ep_len + 0.05:
        raise SystemExit(f"--end ({end}) が配信音声の長さ ({ep_len:.2f}) を越えている")
    bgm_in = measure(bgm)
    gain_db = bgm_lufs - bgm_in["I"]
    span = end - start
    fade_out_at = max(0.0, span - fade_out)
    chain = (f"[1:a]atrim=0:{span:.3f},asetpts=PTS-STARTPTS,volume={gain_db:.2f}dB,"
             f"afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_at:.3f}:d={fade_out},"
             f"adelay={int(round(start * 1000))}:all=1[bgm];"
             f"[0:a][bgm]amix=inputs=2:duration=first:normalize=0[out]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", episode, "-stream_loop", "-1", "-i", bgm,
           "-filter_complex", chain, "-map", "[out]"]
    ext = os.path.splitext(out)[1].lower()
    if ext == ".mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", bitrate]
    elif ext in (".wav",):
        cmd += ["-c:a", "pcm_s16le"]
    elif ext in (".flac",):
        cmd += ["-c:a", "flac"]
    else:
        raise SystemExit(f"出力は .mp3 / .wav / .flac: {out}")
    if title:
        cmd += ["-metadata", f"title={title}"]
    cmd += [out]
    r = run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{r.stderr[-1500:]}")
    result = {
        "episode": episode, "bgm": bgm, "out": out, "start_s": start, "end_s": end,
        "bgm_in_LUFS": bgm_in["I"], "bgm_gain_dB": round(gain_db, 2), "bgm_target_LUFS": bgm_lufs,
        "fade_in_s": fade_in, "fade_out_s": fade_out, "bitrate": bitrate,
        "out_whole": measure(out), "out_len_s": round(duration(out), 3), "episode_len_s": round(ep_len, 3),
    }
    return result


def selftest() -> int:
    """合成音: 30 s の『本編』(1 kHz、 頭 3 s と尾 3 s は無音 = ジングルの代わり) + 4 s の『BGM』(白色雑音、 ループして敷かれる)。
    確かめること: 出力の長さ = 入力の長さ / BGM だけが鳴る区間の音量 ≈ 目標 / ジングルの代わりの無音は無音のまま。"""
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        # 無い環境 (CI の runner 等) は検査不能と申告して 0 = run-all-checks の契約 (違反の exit と分ける)
        print("SKIP: ffmpeg / ffprobe が無い (audio-bgm-underlay selftest)"); return 0
    with tempfile.TemporaryDirectory() as d:
        ep = os.path.join(d, "ep.wav"); bgm = os.path.join(d, "bgm.wav"); out = os.path.join(d, "out.wav")
        # 本編: 3 s 無音 + 24 s トーン (−20 dBFS) + 3 s 無音
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=1000:duration=30",
             "-af", "volume=-20dB,afade=t=in:st=3:d=0.01,afade=t=out:st=26.99:d=0.01,"
                    "volume=enable='lt(t,3)':volume=0,volume=enable='gt(t,27)':volume=0",
             "-ar", "48000", "-ac", "2", ep])
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anoisesrc=color=white:amplitude=0.3:duration=4:sample_rate=48000",
             "-ac", "2", bgm])
        # BGM を 3 s から 27 s まで (= トーンの区間)。 その音量を測るため、 本編の無い版も作る
        res = underlay(ep, bgm, 3.0, 27.0, out, bgm_lufs=-40.0, fade_in=0.5, fade_out=0.5, bitrate="128k", title=None)
        silent = os.path.join(d, "silent.wav")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=30", silent])
        only = os.path.join(d, "only.wav")
        underlay(silent, bgm, 3.0, 27.0, only, bgm_lufs=-40.0, fade_in=0.5, fade_out=0.5, bitrate="128k", title=None)
        bgm_only = measure(only, 4.0, 26.0)["I"]
        head = measure(out, 0.0, 2.9)["I"]
        ok_len = abs(res["out_len_s"] - 30.0) < 0.05
        ok_lvl = abs(bgm_only - (-40.0)) < 1.0
        ok_head = head == -math.inf or head <= -70          # ebur128 は無音を -70 LUFS (測定の床) と出す
        print(f"長さ {res['out_len_s']} s (期待 30) {'✅' if ok_len else '❌'} / BGM 区間 {bgm_only:.1f} LUFS (目標 -40 ± 1) {'✅' if ok_lvl else '❌'} / 頭の無音 {head} {'✅' if ok_head else '❌'}")
        return 0 if (ok_len and ok_lvl and ok_head) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", nargs="?", help="仕上がった配信音声 (ジングル + 本編 + ジングル)")
    ap.add_argument("bgm", nargs="?", help="BGM (ループ素材なら WAV / FLAC。 足りなければ頭から繰り返す)")
    ap.add_argument("--start", type=float, help="BGM を鳴らし始める時刻 (秒、 配信音声の頭から。 = 冒頭ジングルの終わり)")
    ap.add_argument("--end", type=float, help="BGM が消え終わる時刻 (秒。 = 締めのジングルが重なり始める所)")
    ap.add_argument("--bgm-lufs", type=float, default=-40.0, help="BGM 単体の integrated loudness の目標 (既定 -40 = -16 LUFS の声の 24 dB 下)")
    ap.add_argument("--fade-in", type=float, default=4.0)
    ap.add_argument("--fade-out", type=float, default=6.0)
    ap.add_argument("--bitrate", default="128k", help="MP3 のとき")
    ap.add_argument("--title", help="ID3 title (試作と分かる題を)")
    ap.add_argument("--out", help="出力 (.mp3 / .wav / .flac)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.episode and a.bgm and a.start is not None and a.end is not None and a.out):
        ap.error("episode bgm --start --end --out が要る (または --selftest)")
    res = underlay(a.episode, a.bgm, a.start, a.end, a.out, a.bgm_lufs, a.fade_in, a.fade_out, a.bitrate, a.title)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    with open(os.path.splitext(a.out)[0] + ".bgm.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())

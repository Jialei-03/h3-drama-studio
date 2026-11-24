#!/usr/bin/env python3
"""拼接后重建音轨：让音频时长严格等于画面时长。

为什么要重建：concat 直接复制各段 AAC 时，接缝处的时间戳会重叠，解码出来的音频比画面长
（作者的 24 段拼完多出 0.75 s），越往后字幕越晚、最后一个字被截断。
做法：逐段解码已规范化的片段，每段按**它自己的视频帧数**精确截成 n/fps×采样率 个采样（不够补零），
连成一条连续的 PCM，只编码一次（AAC），再和拼好的画面（直接复制，不重编码）合成。

输入：LIST.txt（concat 清单，`file '路径'` 的格式；splice.py 会生成）、VIDEO_IN.mp4（用清单拼好的视频）
输出：OUT.mp4（画面原样复制 + 重建的音轨）；打印两条流的时长和差值

用法示例：
  python3 scripts/fix_audio.py build/full.list.txt build/full_raw.mp4 build/full.mp4
"""
import argparse
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, get, load_config  # noqa: E402


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", "replace")[-400:] if isinstance(e.stderr, bytes) else ""
        sys.exit(f"命令失败（{cmd[0]}，退出码 {e.returncode}）。{err}")


def probe(path, entries, stream=None, extra=()):
    cmd = ["ffprobe", "-v", "error", *extra]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


def decoded_audio_secs(path, sr=48000):
    """把音轨真正解码一遍，数采样得到时长。ffprobe 报的容器时长不可靠：concat 复制 AAC 后，
    容器时长只多几十毫秒，而真正解码出来的音频每个接缝多 ~30 ms（24 段多 0.75 s）。"""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = 0
    while True:
        b = p.stdout.read(1 << 20)
        if not b:
            break
        n += len(b)
    p.wait()
    return n / 4 / sr


def read_list(path):
    """解析 concat 清单：`file '路径'`，支持 '\\'' 转义；相对路径相对于清单所在目录（和 ffmpeg 一致）。"""
    base = os.path.dirname(os.path.abspath(path))
    files = []
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln.startswith("file ") and not ln.startswith("file\t"):
            continue
        p = ln[5:].strip()
        if p.startswith("'") and p.endswith("'") and len(p) >= 2:
            p = p[1:-1].replace("'\\''", "'")
        files.append(p if os.path.isabs(p) else os.path.join(base, p))
    if not files:
        sys.exit(f"清单里没有 file '...' 行：{path}")
    return files


def decode_audio(path, sr):
    """整段解码成 float32 立体声；没有音轨返回 None。"""
    if not probe(path, "stream=codec_type", "a:0"):
        return None
    raw = run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"],
              capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def rebuild(list_path, video_in, out, fps=24.0, sr=48000, bitrate="256k", tolerance=1.0, quiet=False):
    """重建音轨，返回 (画面秒数, 音轨秒数)。splice.py 的 --fix-audio 也调这个函数。"""
    if os.path.abspath(out) == os.path.abspath(video_in):
        sys.exit("OUT 不能和 VIDEO_IN 是同一个文件")
    files = read_list(list_path)
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        sys.exit("清单里的文件不存在：\n  " + "\n  ".join(missing))

    # 逐段数帧，算出每段应有的采样数。用累计取整，避免非整数帧率时每段多/少半个采样累积成漂移。
    counts = [int(probe(f, "stream=nb_read_frames", "v:0", ["-count_frames"]).split()[0]) for f in files]
    total_frames = sum(counts)
    vframes = int(probe(video_in, "stream=nb_read_packets", "v:0", ["-count_packets"]).split()[0])  # 包数 = 帧数，比解码快
    if vframes != total_frames:
        sys.exit(f"清单各段帧数之和 {total_frames} 与 VIDEO_IN 的 {vframes} 帧对不上：清单不是拼这个视频用的那份？")

    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-i", video_in, "-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", "-",
         "-map", "0:v:0", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", out],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    cum_prev = cum = written = 0
    try:
        for f, n in zip(files, counts):
            cum += n
            want = round(cum / fps * sr) - cum_prev          # 本段应有的采样数
            cum_prev += want
            pcm = decode_audio(f, sr)
            if pcm is None:
                pcm = np.zeros((0, 2), np.float32)           # 没有音轨的段整段补静音
            pcm = pcm[:want] if len(pcm) >= want else np.vstack([pcm, np.zeros((want - len(pcm), 2), np.float32)])
            enc.stdin.write(pcm.tobytes())
            written += want
        enc.stdin.close()
    except BrokenPipeError:
        pass
    err = enc.stderr.read().decode("utf-8", "replace")
    if enc.wait() != 0:
        sys.exit(f"ffmpeg 合成失败：{err[-400:]}")

    vd = total_frames / fps
    ad = decoded_audio_secs(out, sr)                       # 解码实测，不信容器时长
    if not quiet:
        print(f"音轨已重建：{written / sr:.3f} s（{total_frames} 帧 / {fps:g} fps）；成品 画面 {vd:.3f} s，音轨解码实测 {ad:.3f} s，差 {ad - vd:+.3f} s")
    if abs(ad - vd) > tolerance / fps:
        sys.exit(f"音画时长差 {ad - vd:+.3f} s 超过 {tolerance:g} 帧，请检查输入")
    return vd, ad


def main():
    ap = argparse.ArgumentParser(description="拼接后重建音轨（音频时长 = 画面时长）")
    ap.add_argument("list", help="concat 清单 LIST.txt")
    ap.add_argument("video_in", help="用这份清单拼好的视频")
    ap.add_argument("out", help="输出 mp4")
    ap.add_argument("--fps", type=float, help="帧率（默认 config 的 project.fps，没有则 24）")
    ap.add_argument("--sr", type=int, default=48000, help="采样率（默认 48000）")
    ap.add_argument("--bitrate", default="256k", help="AAC 码率（默认 256k）")
    ap.add_argument("--tolerance", type=float, default=1.0, help="完成后音画时长差超过这么多帧就报错（默认 1 帧）")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    rebuild(a.list, a.video_in, a.out, a.fps or float(get(cfg, "project.fps", 24)), a.sr, a.bitrate, a.tolerance)


if __name__ == "__main__":
    main()

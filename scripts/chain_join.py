#!/usr/bin/env python3
"""武戏逐段接续的后处理：剪掉上下文帧并做颜色匹配。

生成端把"上一段末尾 N 帧（连同声音）"锚在新一段的第 0 帧上生成，让动作、机位自然接上。
这 N 帧只是上下文，不属于新段的内容，拼接前必须剪掉。本脚本做三件事：
  1. 剪掉 NEW 的前 N 帧，声音同步剪掉同样长度（输出的音画等长）；
  2. 颜色匹配：取"剪掉之后的第一帧"和 PREV 的最后一帧，缩小后逐通道（R/G/B）把均值和标准差对齐，
     按 --strength 的强度（0 = 不改，1 = 完全对齐）把同一套增益和偏移施加到整段；
     修正量过大（增益偏离 1 超过 --max-gain，或偏移超过 --max-offset）说明两帧本来就是不同的东西
     （硬切或白光），不是色彩漂移，此时跳过匹配，只打印提示；
  3. 另出一条接缝预览：PREV 的最后 --secs 秒 + 处理后的新段，专门用来看接缝。

输入：PREV.mp4（上一段）、NEW.mp4（带 N 帧上下文的新一段）
输出（默认和 NEW 放在同一目录，可用 --out-dir 改）：
  <NEW 名>_接.mp4      剪掉上下文、颜色匹配后的片段，进拼接清单
  <NEW 名>_接缝.mp4    接缝预览（--no-seam 可不出）
  stdout 最后一行是 JSON 汇总（输出路径、时长、帧数、增益、偏移）。

用法示例：
  python3 scripts/chain_join.py f6.mp4 f7.mp4 --n 22 --strength 0.75 --secs 3 --out-dir work/
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, get, load_config  # noqa: E402

TH, TW = 216, 384  # 颜色统计用的缩小尺寸


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        sys.exit(f"命令失败（{cmd[0]}，退出码 {e.returncode}）：{' '.join(map(str, cmd[:12]))} ...")


def probe(path, entries, stream=None, extra=()):
    cmd = ["ffprobe", "-v", "error", *extra]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


def count_frames(path):
    # 一律数实际解码帧数，不信容器里写的时长
    return int(probe(path, "stream=nb_read_frames", "v:0", ["-count_frames"]).split()[0])


def has_audio(path):
    return bool(probe(path, "stream=codec_type", "a:0"))


def grab_frame(path, select=None, sseof=None):
    """取一帧缩小成 TW×TH 的 RGB 数组。select=帧序号（精确），sseof=距结尾的秒数（取末帧）。"""
    cmd = ["ffmpeg", "-loglevel", "error"]
    vf = f"scale={TW}:{TH}"
    if sseof is not None:
        cmd += ["-sseof", str(-abs(sseof))]
    if select is not None:
        vf = f"select=eq(n\\,{select})," + vf  # 按帧序号取，避免 -ss 定位的取整误差
    cmd += ["-i", path, "-vf", vf, "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    raw = run(cmd, capture_output=True).stdout
    if len(raw) != TW * TH * 3:
        sys.exit(f"取不到画面：{path}")
    return np.frombuffer(raw, np.uint8).reshape(TH, TW, 3).astype(np.float32)


def color_transfer(src, ref, strength, max_gain, max_offset):
    """逐通道 均值/标准差 对齐，返回 (增益[3], 偏移[3], 是否因修正过大而跳过)。"""
    gain, off = [], []
    for c in range(3):
        ms, ss = src[..., c].mean(), src[..., c].std() + 1e-3
        mr, sr = ref[..., c].mean(), ref[..., c].std() + 1e-3
        g = sr / ss
        o = mr - g * ms
        gain.append(1 + strength * (g - 1))
        off.append(strength * o)
    # 大修正不做：说明两帧是不同的东西（硬切、白光），套上去只会把整段染歪
    if any(abs(g - 1) > max_gain for g in gain) or any(abs(o) > max_offset for o in off):
        return [1.0] * 3, [0.0] * 3, (gain, off)
    return gain, off, None


def main():
    ap = argparse.ArgumentParser(description="武戏接续：剪掉上下文帧 + 颜色匹配 + 接缝预览", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="接缝必看：人物站位/持械手/伤痕是否延续、机位有没有跳变、颜色有没有一跳、声音有没有断或重叠。")
    ap.add_argument("prev", help="上一段（取它的最后一帧做颜色基准）")
    ap.add_argument("new", help="新一段（开头带 N 帧上下文）")
    ap.add_argument("--n", type=int, default=22, help="要剪掉的上下文帧数，必须和生成时锚定的帧数一致（默认 22）")
    ap.add_argument("--strength", type=float, default=0.75, help="颜色匹配强度 0–1（默认 0.75；经验值，未和别的强度对比过）")
    ap.add_argument("--secs", type=float, default=3, help="接缝预览里 PREV 末尾取几秒（默认 3）")
    ap.add_argument("--fps", type=float, help="帧率（默认 config 的 project.fps，没有则 24）")
    ap.add_argument("--width", type=int, help="接缝预览的宽（默认 config 的 project.width，没有则取 NEW 的）")
    ap.add_argument("--height", type=int, help="接缝预览的高（同上）")
    ap.add_argument("--max-gain", type=float, default=0.12, help="增益偏离 1 超过它就跳过颜色匹配（默认 0.12）")
    ap.add_argument("--max-offset", type=float, default=15, help="偏移（0–255 刻度）超过它就跳过颜色匹配（默认 15）")
    ap.add_argument("--no-color", action="store_true", help="只剪帧，不做颜色匹配")
    ap.add_argument("--no-seam", action="store_true", help="不出接缝预览")
    ap.add_argument("--out-dir", help="输出目录（默认和 NEW 同目录）")
    ap.add_argument("--suffix", default="_接", help="输出文件名后缀（默认 _接；拼接清单按这个后缀找最精版本）")
    ap.add_argument("--seam-suffix", default="_接缝")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)

    for p in (a.prev, a.new):
        if not os.path.isfile(p):
            sys.exit(f"找不到文件：{p}")
    fps = a.fps or float(get(cfg, "project.fps", 24))
    total = count_frames(a.new)
    if a.n < 0 or a.n >= total:
        sys.exit(f"--n {a.n} 不合理：NEW 一共只有 {total} 帧")
    keep = total - a.n
    t = a.n / fps
    dur = keep / fps

    # 颜色基准：新片剪掉上下文后的第一帧，对上一段的最后一帧
    gain, off, skipped = [1.0] * 3, [0.0] * 3, None
    if not a.no_color and a.strength > 0:
        src = grab_frame(a.new, select=a.n)
        ref = grab_frame(a.prev, sseof=max(0.05, 1.2 / fps))
        gain, off, skipped = color_transfer(src, ref, a.strength, a.max_gain, a.max_offset)
        if skipped:
            print(f"颜色匹配已跳过（增益 {[round(x, 3) for x in skipped[0]]}，偏移 {[round(x, 1) for x in skipped[1]]}）："
                  "两帧差别太大，多半是硬切或白光，不是色彩漂移", file=sys.stderr)

    base = os.path.splitext(os.path.basename(a.new))[0]
    out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.new))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, base + a.suffix + ".mp4")
    seam = os.path.join(out_dir, base + a.seam_suffix + ".mp4")

    vf = f"trim=start_frame={a.n},setpts=PTS-STARTPTS"
    if any(abs(g - 1) > 1e-6 for g in gain) or any(abs(o) > 1e-6 for o in off):
        lut = ":".join(f"{ch}='clip(val*{g:.4f}+{o:.2f},0,255)'" for ch, g, o in zip("rgb", gain, off))
        vf += f",lutrgb={lut}"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", a.new, "-vf", vf, "-frames:v", str(keep),
           "-c:v", "libx264", "-crf", str(a.crf), "-preset", a.preset, "-pix_fmt", "yuv420p"]
    audio = has_audio(a.new)
    if audio:
        # 声音从同样的时刻剪起，再补静音/截到和画面一样长，音画等长（拼接规范化时不用再补偿）
        cmd += ["-af", f"atrim=start={t:.6f},asetpts=PTS-STARTPTS,apad,atrim=end={dur:.6f},asetpts=PTS-STARTPTS",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    run(cmd + [out])

    if not a.no_seam:
        w = a.width or get(cfg, "project.width") or int(probe(a.new, "stream=width", "v:0").split()[0])
        h = a.height or get(cfg, "project.height") or int(probe(a.new, "stream=height", "v:0").split()[0])
        both_audio = audio and has_audio(a.prev)
        norm = f"scale={w}:{h},fps={fps},setsar=1"
        fc = f"[0:v]{norm}[v0];[1:v]{norm}[v1];"
        if both_audio:
            an = "aresample=48000,aformat=channel_layouts=stereo"
            fc += f"[0:a]{an}[a0];[1:a]{an}[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
        else:
            fc += "[v0][v1]concat=n=2:v=1:a=0[v]"
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-sseof", f"-{a.secs}", "-i", a.prev, "-i", out, "-filter_complex", fc,
               "-map", "[v]"] + (["-map", "[a]", "-c:a", "aac"] if both_audio else ["-an"]) + ["-c:v", "libx264", "-crf", "17", seam]
        run(cmd)

    d = float(probe(out, "format=duration"))
    print(json.dumps({"out": out, "seam": None if a.no_seam else seam, "frames": keep, "secs": round(d, 3),
                      "gain": [round(x, 3) for x in gain], "offset": [round(x, 1) for x in off],
                      "color_skipped": bool(skipped) or a.no_color}, ensure_ascii=False))


if __name__ == "__main__":
    main()

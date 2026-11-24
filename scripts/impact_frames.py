#!/usr/bin/env python3
"""冲击帧：在真正的大招上叠几帧一闪而过的 2D 冲击画面（后期插入，不是视频生成时画的）。

每处冲击 = 一张九宫格图（图像模型出的 3×3 冲击画面）+ 一行位置表。排法（24 fps，定稿参数，见 impact-frames.md）：
  每格停留 2 帧：第 1 帧放大到 108%、第 2 帧回到 100%（放大回弹），格与格之间隔 1 帧原画面（所以画面一直在动，不会像停住）；
  最亮的那一格从"声响峰值那一帧"开始，之前的格向前排；
  需要时（爆炸、白光吞没这类"结果瞬间"）在最后一格之后接 负片×3、原画面×2、负片×3。
只换画面，帧数不变，音轨原样复制（-c:a copy）。会丢掉封面流，封面在字幕之后再嵌。

输入：
  IN.mp4         成片（帧号对应这一版的时间线；剪过片要把帧号一起平移，见 shifts）
  IMPACTS.yaml   冲击表，示例见 examples/gemini-revenge/data/impacts.example.yaml
输出：OUT.mp4（同长度）；终端打印每一帧换成了什么。

用法示例：
  python3 scripts/impact_frames.py impacts.yaml film.mp4 film_impact.mp4 --dry-run   # 先看时间表
  python3 scripts/impact_frames.py impacts.yaml film.mp4 film_impact.mp4
  python3 scripts/impact_frames.py --find-peak 100.0,104.0 film.mp4                  # 找声响峰值帧/最亮帧（再用肉眼确认）
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, get, load_config  # noqa: E402


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", "replace")[-600:] if isinstance(e.stderr, bytes) else ""
        sys.exit(f"命令失败（{cmd[0]}，退出码 {e.returncode}）：{err}")


def probe(path, entries, stream=None, extra=()):
    cmd = ["ffprobe", "-v", "error", *extra] + (["-select_streams", stream] if stream else []) + ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------------------ 找峰值
def find_peak(src, t0, t1, fps, top=5):
    """在 [t0, t1] 秒里按"每帧音频 RMS"和"每帧平均亮度"各列出最突出的几帧（帧号 = 本片时间线）。仅作定位提示，必须肉眼确认。"""
    sr = 48000
    raw = run(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", src, "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
              capture_output=True).stdout
    au = np.frombuffer(raw, np.float32)
    spf = sr / fps
    nf = int(len(au) // spf)
    rms = np.array([np.sqrt(np.mean(au[int(i * spf):int((i + 1) * spf)] ** 2)) for i in range(nf)])
    raw = run(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", src, "-vf", "scale=64:36,format=gray", "-f", "rawvideo", "-"],
              capture_output=True).stdout
    vid = np.frombuffer(raw, np.uint8).reshape(-1, 36 * 64).astype(np.float32)
    luma = vid.mean(1)
    base = int(round(t0 * fps))
    print(f"区间 {t0}–{t1} s（帧 {base}–{base + len(luma)}）")
    print("声音最响的帧（RMS）：", ", ".join(f"{base + int(i)}" for i in np.argsort(-rms)[:top]))
    print("最亮的帧（平均亮度）：", ", ".join(f"{base + int(i)}" for i in np.argsort(-luma)[:top]))
    jump = np.diff(luma, prepend=luma[0])
    print("亮度突增最大的帧：   ", ", ".join(f"{base + int(i)}" for i in np.argsort(-jump)[:top]))
    print("峰值帧 = 声响和白光撞在一起的那一帧；把它填进表里的 peak_frame，再截图肉眼确认。")


# ------------------------------------------------------------------ 时间表
def make_shift(shifts):
    return lambda n: n + sum(d for at, d in shifts if n >= at)


def build_schedule(impacts, base, shift):
    """返回 {帧号: (impact 序号, 格号, 放大?) 或 (impact 序号, 'neg')}。格号从 1 起，按九宫格从左到右、从上到下数。"""
    sched, owner = {}, {}

    def put(n, v, name):
        if n in sched:
            sys.exit(f"帧 {n} 被两处冲击同时用到（{owner[n]} 和 {name}）：检查帧号或缩短格数")
        sched[n], owner[n] = v, name

    for k, im in enumerate(impacts):
        c = {**base, **im}
        name = c.get("name") or f"#{k + 1}"
        P, G = int(c["panel_frames"]), int(c["gap_frames"])
        slot = P + G
        before, after = list(c.get("before") or []), list(c.get("after") or [])
        seq = before + [int(c.get("peak_panel", 4))] + after
        peak = shift(int(c["peak_frame"]))
        start = peak - slot * len(before)               # 最亮格从峰值帧开始，之前的格向前排
        for i, p in enumerate(seq):
            n = start + slot * i
            for d in range(P):
                put(n + d, (k, int(p), d == 0), name)   # 每格第 1 帧放大，其余帧回到 100%
        if c.get("negative"):
            n0 = start + slot * len(seq) + int(c["negative_delay"])
            for d, ch in enumerate(c["negative_pattern"]):
                if ch == "#":
                    put(n0 + d, (k, "neg"), name)
    return sched


def panel_image(path, layout, p, zoom, W, H, margin, out):
    """从九宫格里裁第 p 格（四周各让 margin 像素去掉分隔线），可选从中心裁 1/zoom 再放大，缩放到全画幅。"""
    rows, cols = layout
    if not 1 <= p <= rows * cols:
        sys.exit(f"格号 {p} 超出 {rows}×{cols} 的范围（格号从 1 起，从左到右、从上到下）")
    im = Image.open(path).convert("RGB")
    cw, ch = im.size[0] / cols, im.size[1] / rows
    x, y = ((p - 1) % cols) * cw, ((p - 1) // cols) * ch
    c = im.crop((int(x) + margin, int(y) + margin, int(x + cw) - margin, int(y + ch) - margin))
    if zoom > 1:
        w, h = c.size
        dw, dh = w * (1 - 1 / zoom) / 2, h * (1 - 1 / zoom) / 2
        c = c.crop((int(dw), int(dh), int(w - dw), int(h - dh)))
    c.resize((W, H), Image.LANCZOS).save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description="冲击帧：九宫格 + 位置表 → 在指定帧上叠图 / 负片", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="表里的字段：fps、zoom、panel_frames、gap_frames、margin、negative_pattern、negative_delay、shifts，"
                                        "以及 impacts[].{name, grid, layout, peak_frame, peak_panel, before, after, negative}。格号从 1 起。")
    ap.add_argument("files", nargs="+", metavar="IMPACTS.yaml IN.mp4 OUT.mp4", help="冲击表、成片、输出（--dry-run 时可省输出；--find-peak 时只给成片）")
    ap.add_argument("--dry-run", action="store_true", help="只打印时间表，不渲染")
    ap.add_argument("--find-peak", metavar="起,止", help="不渲染：在这段秒数里找声音/亮度峰值帧（此时第一个位置参数是 IN.mp4，不用写 IMPACTS）")
    ap.add_argument("--panel-dir", help="把裁好的格子图存到这个目录（默认临时目录，用完删除）")
    ap.add_argument("--fps", type=float, help="帧率（默认 表里的 fps > config project.fps > 24）")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)

    if a.find_peak:                                    # impact_frames.py --find-peak 100,104 film.mp4
        if len(a.files) != 1 or not os.path.isfile(a.files[0]):
            ap.error("--find-peak 只需要一个位置参数：成片 IN.mp4")
        t0, t1 = (float(x) for x in a.find_peak.split(","))
        find_peak(a.files[0], t0, t1, a.fps or float(get(cfg, "project.fps", 24)))
        return
    if len(a.files) not in (2, 3) or (len(a.files) == 2 and not a.dry_run):
        ap.error("需要 IMPACTS.yaml IN.mp4 OUT.mp4（--dry-run 时 OUT 可省）")
    a.impacts, a.src = a.files[0], a.files[1]
    a.out = a.files[2] if len(a.files) == 3 else None
    if not os.path.isfile(a.src):
        sys.exit(f"找不到成片：{a.src}")
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.src):
        sys.exit("OUT 不能和 IN 是同一个文件")
    try:
        import yaml
    except ImportError:
        sys.exit("缺少 PyYAML：pip install pyyaml")
    ypath = os.path.abspath(a.impacts)
    tab = yaml.safe_load(open(ypath, encoding="utf-8")) or {}
    impacts = tab.get("impacts") or []
    if not impacts:
        sys.exit("冲击表里没有 impacts")
    fps = a.fps or float(tab.get("fps") or get(cfg, "project.fps", 24))
    base = dict(zoom=float(tab.get("zoom", 1.08)), panel_frames=int(tab.get("panel_frames", 2)), gap_frames=int(tab.get("gap_frames", 1)),
                margin=int(tab.get("margin", 5)), negative_pattern=str(tab.get("negative_pattern", "###..###")),
                negative_delay=int(tab.get("negative_delay", 1)), layout=str(tab.get("layout", "3x3")))
    shifts = [(int(s["at_frame"]), int(s["delta_frames"])) for s in (tab.get("shifts") or [])]
    sched = build_schedule(impacts, base, make_shift(shifts))

    W, H = (int(x) for x in probe(a.src, "stream=width,height", "v:0").split(",")[:2])
    nframes = int(probe(a.src, "stream=nb_read_packets", "v:0", ["-count_packets"]).split()[0])
    if min(sched) < 0 or max(sched) >= nframes:
        sys.exit(f"时间表用到了第 {min(sched)}–{max(sched)} 帧，但成片只有 {nframes} 帧（0–{nframes - 1}）：检查帧号和 shifts")

    print(f"{W}x{H}，{nframes} 帧；共 {len(impacts)} 处冲击，改动 {len(sched)} 帧")
    for k, im in enumerate(impacts):
        fr = sorted(n for n, v in sched.items() if v[0] == k)
        desc = []
        for n in fr:
            v = sched[n]
            desc.append(f"{n}:负片" if v[1] == "neg" else f"{n}:格{v[1]}{'↑' if v[2] else ''}")
        print(f"  {im.get('name') or '#' + str(k + 1)}（峰值帧 {im['peak_frame']}）  " + " ".join(desc))
    if a.dry_run:
        return

    for k, im in enumerate(impacts):
        g = os.path.expanduser(im["grid"])
        im["_grid"] = g if os.path.isabs(g) else os.path.join(os.path.dirname(ypath), g)
        if not os.path.isfile(im["_grid"]):
            sys.exit(f"找不到九宫格图：{im['_grid']}")

    tmp = tempfile.TemporaryDirectory() if not a.panel_dir else None
    pdir = a.panel_dir or tmp.name
    os.makedirs(pdir, exist_ok=True)
    try:
        images = {}                                    # (impact, 格, 放大?) -> 文件
        for n, v in sorted(sched.items()):
            if v[1] == "neg" or v in images:
                continue
            k, p, zoomed = v
            c = {**base, **impacts[k]}
            r, cl = (int(x) for x in str(c["layout"]).lower().split("x"))
            images[v] = panel_image(impacts[k]["_grid"], (r, cl), p, float(c["zoom"]) if zoomed else 1.0, W, H, int(c["margin"]),
                                    os.path.join(pdir, f"imp{k + 1}_p{p}_{'z' if zoomed else 'n'}.png"))
        keys = sorted(images)
        inputs = sum((["-i", images[v]] for v in keys), [])
        chains, last = [], "0:v"
        for i, v in enumerate(keys, 1):
            en = "+".join(f"eq(n,{n})" for n, x in sorted(sched.items()) if x == v)
            chains.append(f"[{last}][{i}:v]overlay=enable='{en}'[o{i}]")
            last = f"o{i}"
        negs = sorted(n for n, v in sched.items() if v[1] == "neg")
        if negs:  # 负片：把整幅画面反色，只在这几帧上叠回去
            chains.append(f"[{last}]split[a][b];[b]negate[bn];[a][bn]overlay=enable='" + "+".join(f"eq(n,{n})" for n in negs) + "'[vout]")
            last = "vout"
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", a.src] + inputs + ["-filter_complex", ";".join(chains), "-map", f"[{last}]" if last != "0:v" else "0:v",
               "-map", "0:a?", "-c:v", "libx264", "-crf", str(a.crf), "-preset", a.preset, "-pix_fmt", "yuv420p", "-c:a", "copy",
               "-movflags", "+faststart", a.out]
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        run(cmd, stderr=subprocess.PIPE)
    finally:
        if tmp:
            tmp.cleanup()
    print("OK", a.out)
    # 核对：帧数不变（只换画面）
    n_out = int(probe(a.out, "stream=nb_read_packets", "v:0", ["-count_packets"]).split()[0])
    if n_out != nframes:
        print(f"警告：输出 {n_out} 帧，输入 {nframes} 帧", file=sys.stderr)


if __name__ == "__main__":
    main()

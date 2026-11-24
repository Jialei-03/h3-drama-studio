#!/usr/bin/env python3
"""按片段清单拼接：逐段规范化，再用 concat 拼成整片。

清单是一份 yaml：每条一个片段，按播放顺序；每条有文件、可选的裁剪起止帧、可选的分组。见
examples/gemini-revenge/data/clips.example.yaml。

每一段先单独转成**完全一致**的格式再拼（concat 直接复制要求所有流参数一致）：
  画面 缩放到 宽×高、setsar=1、fps 统一，H.264 crf 16 preset slow yuv420p；
  声音 48 kHz 双声道，先补静音再截到**和画面一样长**，AAC 192k；没有音轨的段补静音；
  帧数 用 ffprobe -count_frames 数实际帧数，输出 -frames:v 钉死，不信容器里的时长。
  逐段强制音画等长，是为了让误差不跨段累计。
规范化结果按（源文件、裁剪、规格）缓存在工作目录，清单里只改一行时，其余段不重新编码。

同一段有多个版本时取"最精"的：对清单里的文件 X.mp4，依次找 X_接剪.mp4、X_接.mp4（--prefer-suffixes 可改），
取存在的第一个，都没有才用 X.mp4。接续段（chain: true）不允许退回原片：原片头部还带着上下文帧。

拼完后音频会比画面长（concat 复制 AAC 的时间戳在接缝重叠），所以紧接着要重建音轨：
  python3 scripts/fix_audio.py <清单.list.txt> <拼好的.mp4> <输出.mp4>
或者加 --fix-audio 一步做完（等价）。

输入：CLIPS.yaml    输出：-o 指定的 mp4（或 yaml 里的 output）+ 同名 .list.txt（concat 清单，放在工作目录）
用法示例：
  python3 scripts/splice.py clips.yaml -o build/full.mp4 --fix-audio
  python3 scripts/splice.py clips.yaml -o build/fight_only.mp4 --group fight --fix-audio
"""
import argparse
import hashlib
import os
import subprocess
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, get, load_config  # noqa: E402


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", "replace")[-500:] if isinstance(e.stderr, bytes) else ""
        sys.exit(f"命令失败（{cmd[0]}，退出码 {e.returncode}）：{err}")


def probe(path, entries, stream=None, extra=()):
    cmd = ["ffprobe", "-v", "error", *extra]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


def src_info(path):
    """(实际帧数, 源帧率 Fraction, 是否有音轨)"""
    n = int(probe(path, "stream=nb_read_frames", "v:0", ["-count_frames"]).split()[0])
    r = probe(path, "stream=avg_frame_rate", "v:0").split()[0]
    if r in ("0/0", ""):
        r = probe(path, "stream=r_frame_rate", "v:0").split()[0]
    return n, Fraction(r), bool(probe(path, "stream=codec_type", "a:0"))


def resolve(entry, base, prefer, exact_all):
    """返回 (实际用的文件, 试过的候选列表)。file 可以是字符串，也可以是候选列表（第一个存在的赢）。"""
    f = entry.get("file")
    if not f:
        sys.exit(f"清单里有一条没有 file：{entry}")
    cands = []
    for p in ([f] if isinstance(f, str) else list(f)):
        p = os.path.expanduser(p)
        p = p if os.path.isabs(p) else os.path.join(base, p)
        if not entry.get("exact", exact_all) and isinstance(f, str):
            stem, ext = os.path.splitext(p)
            cands += [stem + s + ext for s in prefer]
        cands.append(p)
    for c in cands:
        if os.path.isfile(c):
            return c, cands
    return None, cands


def normalise(src, dst, start, end, n, srcfps, has_a, W, H, fps, crf, preset, sr):
    """把 src 的第 [start, end) 帧规范化成 dst。返回输出帧数（期望值）。"""
    n_out = end - start if srcfps == fps else round((end - start) / float(srcfps) * float(fps))
    dur = n_out / float(fps)
    vf = []
    if start > 0 or end < n:
        vf.append(f"trim=start_frame={start}:end_frame={end}")
        vf.append("setpts=PTS-STARTPTS")
    vf.append(f"scale={W}:{H},setsar=1,fps={fps}")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", src]
    if has_a:
        af = []
        if start > 0 or end < n:
            af.append(f"atrim=start={start / float(srcfps):.6f}:end={end / float(srcfps):.6f}")
            af.append("asetpts=PTS-STARTPTS")
        # 补静音再截到画面长度：音频比画面短或长几十毫秒，拼出来就整体错位，越往后越明显
        af += [f"aresample={sr}", "apad", f"atrim=end={dur:.6f}", "asetpts=PTS-STARTPTS"]
        cmd += ["-vf", ",".join(vf), "-af", ",".join(af), "-map", "0:v:0", "-map", "0:a:0"]
    else:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=stereo", "-vf", ",".join(vf), "-map", "0:v:0", "-map", "1:a", "-t", f"{dur:.6f}"]
    cmd += ["-ac", "2", "-frames:v", str(n_out), "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(sr), dst]
    run(cmd, stderr=subprocess.PIPE)
    return n_out


def main():
    ap = argparse.ArgumentParser(description="按片段清单（yaml）规范化并拼接", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="清单字段：output、width/height/fps、prefer_suffixes、clips[].{file,start_frame,end_frame,group,chain,exact,label}。"
                                        "start_frame 含、end_frame 不含，按所选文件自己的帧序号数（从 0 起）。清单里的相对路径相对清单文件所在目录。")
    ap.add_argument("clips", help="片段清单 CLIPS.yaml")
    ap.add_argument("-o", "--output", help="输出 mp4（覆盖清单里的 output）")
    ap.add_argument("--group", action="append", help="只拼 group 等于它的片段（可重复）；不给就拼全部")
    ap.add_argument("--work-dir", help="规范化片段和 concat 清单的存放目录（默认：输出目录/_splice_work）")
    ap.add_argument("--fix-audio", action="store_true", help="拼完直接重建音轨（等价于再跑一次 fix_audio.py）")
    ap.add_argument("--dry-run", action="store_true", help="只列出每段实际用哪个文件、多少帧，不编码")
    ap.add_argument("--fps", type=float, help="帧率（默认 清单 > config project.fps > 24）")
    ap.add_argument("--width", type=int, help="宽（默认 清单 > config project.width > 1536）")
    ap.add_argument("--height", type=int, help="高（默认 清单 > config project.height > 864）")
    ap.add_argument("--prefer-suffixes", help="最精版本的后缀，逗号分隔，靠前的优先（默认 _接剪,_接；写成空串关闭）")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--sr", type=int, default=48000)
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)

    try:
        import yaml
    except ImportError:
        sys.exit("缺少 PyYAML：pip install pyyaml")
    mpath = os.path.abspath(a.clips)
    man = yaml.safe_load(open(mpath, encoding="utf-8")) or {}
    base = os.path.dirname(mpath)
    clips = man.get("clips") or []
    if not clips:
        sys.exit("清单里没有 clips")
    fps = Fraction(str(a.fps or man.get("fps") or get(cfg, "project.fps", 24))).limit_denominator(1001)
    W = int(a.width or man.get("width") or get(cfg, "project.width", 1536))
    H = int(a.height or man.get("height") or get(cfg, "project.height", 864))
    if a.prefer_suffixes is not None:
        prefer = [s for s in a.prefer_suffixes.split(",") if s]
    else:
        prefer = man.get("prefer_suffixes", ["_接剪", "_接"]) or []
    out = a.output or man.get("output")
    if not out and not a.dry_run:
        sys.exit("没有输出路径：用 -o 或在清单里写 output")
    out = os.path.abspath(out if a.output else os.path.join(base, os.path.expanduser(out or "dry_run.mp4")))
    work = os.path.abspath(a.work_dir) if a.work_dir else os.path.join(os.path.dirname(out), "_splice_work")

    if a.group:
        want = set(a.group)
        clips = [c for c in clips if want & set([c["group"]] if isinstance(c.get("group"), str) else (c.get("group") or []))]
        if not clips:
            sys.exit(f"没有 group 属于 {sorted(want)} 的片段")

    # 1. 解析每段实际用哪个文件；缺的一次列全
    plan, missing = [], []
    for i, c in enumerate(clips, 1):
        f, cands = resolve(c, base, prefer, False)
        if f is None:
            missing.append((i, cands))
            continue
        raw = cands[-1]
        if c.get("chain") and os.path.abspath(f) == os.path.abspath(raw) and prefer:
            sys.exit(f"第 {i} 条是接续段（chain: true），但找不到它的 {'/'.join(prefer)} 版本，不能拿原片拼（头部带着上下文帧）：{raw}")
        n, sfps, has_a = src_info(f)
        s = int(c.get("start_frame") or 0)
        e = int(c.get("end_frame") or n)
        if not (0 <= s < e <= n):
            sys.exit(f"第 {i} 条的裁剪范围不对：start_frame={s}, end_frame={e}，该文件只有 {n} 帧（{f}）")
        plan.append(dict(i=i, file=f, n=n, sfps=sfps, has_a=has_a, start=s, end=e, label=c.get("label") or os.path.basename(f)))
    if missing:
        sys.exit("找不到文件：\n" + "\n".join(f"  第 {i} 条，试过：{' | '.join(cs)}" for i, cs in missing))

    print(f"规格 {W}x{H} @ {float(fps):g} fps，共 {len(plan)} 段")
    for p in plan:
        warn = "" if p["has_a"] else "（无音轨，补静音）"
        trim = f"  裁剪 [{p['start']}, {p['end']})" if (p["start"] > 0 or p["end"] < p["n"]) else ""
        print(f"  {p['i']:>3}  {p['label']}  {p['end'] - p['start']}/{p['n']} 帧{trim}{warn}")
    if a.dry_run:
        return

    # 2. 逐段规范化（带缓存）
    os.makedirs(work, exist_ok=True)
    listed, total = [], 0
    for p in plan:
        st = os.stat(p["file"])
        key = "|".join(map(str, (os.path.abspath(p["file"]), st.st_size, st.st_mtime_ns, p["start"], p["end"], W, H, fps, a.crf, a.preset, a.sr)))
        stem = os.path.splitext(os.path.basename(p["file"]))[0]
        dst = os.path.join(work, f"{stem}_{hashlib.sha1(key.encode()).hexdigest()[:8]}.mp4")
        n_out = p["end"] - p["start"] if p["sfps"] == fps else round((p["end"] - p["start"]) / float(p["sfps"]) * float(fps))
        if not os.path.isfile(dst):
            normalise(p["file"], dst, p["start"], p["end"], p["n"], p["sfps"], p["has_a"], W, H, fps, a.crf, a.preset, a.sr)
            got = int(probe(dst, "stream=nb_read_frames", "v:0", ["-count_frames"]).split()[0])
            if got != n_out:
                print(f"  警告：{p['label']} 规范化后 {got} 帧，预期 {n_out}（帧率转换会有 ±1 帧）；音轨重建时以实际帧数为准", file=sys.stderr)
        listed.append(dst)
        total += n_out

    # 3. concat 拼接（画面和已规范化的 AAC 直接复制）
    os.makedirs(os.path.dirname(out), exist_ok=True)
    lst = os.path.join(work, os.path.splitext(os.path.basename(out))[0] + ".list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for d in listed:
            fh.write("file '" + d.replace("'", "'\\''") + "'\n")
    raw_out = os.path.join(work, os.path.splitext(os.path.basename(out))[0] + ".raw.mp4") if a.fix_audio else out
    run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", raw_out],
        stderr=subprocess.PIPE)

    if a.fix_audio:
        from fix_audio import rebuild
        rebuild(lst, raw_out, out, float(fps), a.sr)
        os.remove(raw_out)

    from fix_audio import decoded_audio_secs
    vd = total / float(fps)
    ad = decoded_audio_secs(out, a.sr)               # 解码实测；容器时长会低估 concat 造成的偏长
    print(f"OK {out}\n  {total} 帧 = {vd:.3f} s；音轨解码实测 {ad:.3f} s，差 {ad - vd:+.3f} s；concat 清单 {lst}")
    if not a.fix_audio:
        # concat 复制 AAC 会让音轨偏长（每个接缝约 30 ms，段越多越明显），拼接后必须重建；字幕、配乐的时间都要在重建后的音轨上测
        print(f"  下一步（必做）重建音轨：python3 scripts/fix_audio.py {lst} {out} <输出.mp4>"
              + (f"\n  当前音轨比画面{'长' if ad > vd else '短'} {abs(ad - vd):.3f} s" if abs(ad - vd) > 1 / float(fps) else ""))

if __name__ == "__main__":
    main()

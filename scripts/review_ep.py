#!/usr/bin/env python3
"""验片：对一批渲好的片段自动检查——硬切数、听写台词对剧本、用时，并可截八帧联系表。

输入：shots.json（剧本在里面：每段提示词里的 [Shot N] 和 <d>台词</d>）、渲好的片段所在目录（文件名 <id>_t<take>.mp4）、
      可选 results.json（队列记录，用来写用时和状态）。
输出：一份 markdown 检查清单（默认写在片段目录里，叫 review_<take>.md），每段包括：
  - 镜头：提示词写了 N 个，应检测到 N-1 个硬切；数量不符标“镜头数不符”；
  - 台词：每句 <d>…</d> 是否在听写里出现（剧本字符有六成以上按顺序出现记 ✓）；英文台词不比对；
  - 听写原文；加 --sheet 还会为每段生成 <key>.sheet.jpg（八帧联系表，每格标时间）。
自动检查只用来排出“先看哪几段”，**以眼睛和耳朵为准**：起跳、冲击、闪光会被当成切点（误报）；同音字听写会错（✗ 不等于念错）。
听写依赖 mlx-whisper 或 openai-whisper（可选，见 asr.py）；没有就加 --no-asr，只做切点和截帧。依赖 ffmpeg、numpy。

用法示例：
  python3 scripts/review_ep.py --shots shots.json --videos renders/ --take 530 --sheet
  python3 scripts/review_ep.py --shots shots.json --videos renders/ --only f1,f2 --no-asr

状态：本机用一段真实带台词的片子验证了切点检测、听写比对和截帧；批量多段、接续段的路径只用示例数据走过，未在干净环境端到端验证。
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import add_config_arg, get, load_config  # noqa: E402


def cuts(path, fps=24, min_diff=18.0, ratio=6.0):
    """把视频缩成 160×90 灰度图，相邻帧差超过 max(min_diff, ratio×中位数) 记为一个硬切；返回时间（秒）列表。
    阈值为什么取这两个：纯 min_diff 在慢镜头里漏切，纯倍数在整段都剧烈运动时满屏误报。"""
    W, H = 160, 90
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    if len(raw) < 2 * W * H:
        return []
    a = np.frombuffer(raw[: len(raw) // (W * H) * (W * H)], np.uint8).reshape(-1, H, W).astype(np.float32)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    med = np.median(d)
    return [round((i + 1) / fps, 2) for i in range(len(d)) if d[i] > max(min_diff, ratio * med)]


def sheet(video, out, n_frames, fps=24):
    """八帧联系表：4×2，每格 400×226，标时间。"""
    from PIL import Image, ImageDraw
    dur = n_frames / fps
    im = Image.new("RGB", (400 * 4, 247 * 2), "#17252c")
    d = ImageDraw.Draw(im)
    for j in range(8):
        t = dur * (j + 0.5) / 8
        buf = subprocess.check_output(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=400:226", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
        x, y = j % 4 * 400, j // 4 * 247
        im.paste(Image.frombytes("RGB", (400, 226), buf), (x, y))
        d.text((x + 6, y + 229), f"{t:.1f}s", fill="white")
    im.save(out, quality=82)


def count_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def norm(s):
    return re.sub(r"[^一-鿿\w]", "", s).replace("_", "")


def has_cjk(s):
    return bool(re.search(r"[一-鿿]", s))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shots", required=True, help="shots.json")
    ap.add_argument("--videos", required=True, help="渲好的片段所在目录（<id>_t<take>.mp4）")
    ap.add_argument("--results", help="队列的 results.json（可选：写用时和状态）")
    ap.add_argument("--take", help="只验这一轮：shots.json 里 take 等于它的那些段")
    ap.add_argument("--only", help="只验这几段，逗号分隔的 id")
    ap.add_argument("--out", help="检查清单 md 路径（默认：<videos>/review_<take>.md）")
    ap.add_argument("--sheet", action="store_true", help="每段另生成八帧联系表 <key>.sheet.jpg（放在 --out 同目录）")
    ap.add_argument("--no-asr", action="store_true", help="不听写，只做切点和截帧")
    ap.add_argument("--lang", default="zh", help="听写语言，默认 zh")
    ap.add_argument("--match", type=float, default=0.6, help="台词判 ✓ 的字符比例，默认 0.6")
    ap.add_argument("--cache", default="asr_cache", help="听写缓存目录")
    ap.add_argument("--offline", action="store_true", help="听写模型已在本地时不联网")
    ap.add_argument("--backend", choices=["auto", "mlx", "openai"], default="auto")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    fps = float(get(cfg, "project.fps", 24))
    vdir = Path(a.videos)
    if not vdir.is_dir():
        sys.exit(f"片段目录不存在：{vdir}")
    shots = json.loads(Path(a.shots).read_text(encoding="utf-8"))
    if a.take:
        shots = [s for s in shots if str(s.get("take", 1)) == str(a.take)]
    if a.only:
        keep = set(a.only.split(","))
        shots = [s for s in shots if s["id"] in keep]
    if not shots:
        sys.exit("没有选中任何段（检查 --take / --only）")
    res = json.loads(Path(a.results).read_text(encoding="utf-8")) if a.results else {}
    asr = None
    if not a.no_asr:
        import asr as asr_mod  # 失败（没装听写库）时给出清楚的报错
        asr = asr_mod
        asr._backend(a.backend)
    out = Path(a.out) if a.out else vdir / f"review_{a.take or 'all'}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, flagged = [], []
    for s in shots:
        sid, key = s["id"], f"{s['id']}_t{s.get('take', 1)}"
        f = vdir / f"{key}.mp4"
        r = res.get(key, {})
        if not f.exists():
            rows.append(f"## {sid}（{key}）\n\n状态：{r.get('status', '没有找到视频')}\n")
            continue
        n_shots = len(set(re.findall(r"^\[Shot (\d+)\]", s["prompt"], re.M)))
        raw_lines = [re.sub(r"^\s*\[[^\]]*\]\s*", "", l).strip() for l in re.findall(r"<d>(.*?)</d>", s["prompt"], re.S)]
        c = cuts(f, fps)
        nfr = count_frames(f)
        lead = s.get("ctx_frames", 22) if s.get("ctx") else 0
        row = [f"## {sid}　（{key}" + (f"，{r['seconds_wall']} 秒" if r.get("seconds_wall") else "") + (f"，{r['finished']} 完成" if r.get("finished") else "") + "）\n",
               f"- 视频：`{f.name}`，{nfr} 帧 = {nfr / fps:.2f} 秒" + (f"；前 {lead} 帧（{lead / fps:.2f} 秒）是接续上一段的，拼接时剪掉，下面的时间含这一段" if lead else ""),
               f"- 镜头：写了 {n_shots} 个，检测到硬切 {len(c)} 处 {c}" + ("" if len(c) == n_shots - 1 else "　⚠ 镜头数不符（起跳、冲击、闪光会被当成切点；对着联系表看一眼）")]
        if len(c) != n_shots - 1:
            flagged.append(sid)
        if a.sheet:
            sp = out.parent / f"{key}.sheet.jpg"
            try:
                sheet(f, sp, nfr, fps)
                row.append(f"- 联系表：`{sp.name}`")
            except Exception as e:
                row.append(f"- 联系表失败：{str(e)[:100]}")
        if asr:
            tr = asr.transcribe(f, a.lang, a.backend, None, None, a.cache or None, a.offline)
            segs, heard = tr["segments"], norm("".join(t for _, _, t in tr["segments"]))
            lc = []
            for l in raw_lines:
                if not has_cjk(l):
                    lc.append(f"  - ·（非中文，未比对）{l}")
                    continue
                m = difflib.SequenceMatcher(None, norm(l), heard, autojunk=False)  # 剧本字符中按顺序出现在听写里的比例；同音字仍会 miss
                share = sum(b.size for b in m.get_matching_blocks()) / max(1, len(norm(l)))
                lc.append(f"  - {'✓' if share > a.match else '✗'} {l}")
                if share <= a.match:
                    flagged.append(sid)
            row.append("- 台词（✓ = 听写对上 %d%% 以上；同音字会错，✗ 不等于念错）：" % (a.match * 100) + ("\n" + "\n".join(lc) if lc else "无"))
            row.append("- 听写原文：" + (" ｜ ".join(f"{x:.1f}-{y:.1f}s {t.strip()}" for x, y, t in segs) or "（没有听到人声）"))
        rows.append("\n".join(row) + "\n")
    head = (f"# 自动检查（take {a.take or '全部'}，{len(shots)} 段）\n\n自动结果只用来排出先看哪几段，以眼睛和耳朵为准。听写用 whisper，同音字会写错。\n\n"
            + (f"**需要先看的段：{', '.join(sorted(set(flagged)))}**\n\n" if flagged else ""))
    out.write_text(head + "\n".join(rows), encoding="utf-8")
    print(head + "\n".join(rows))
    print(f"\n已写 {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""电影感对白字幕：每张字幕卡画成一张透明 PNG（文字 + 柔和阴影 + 细暗边），再用 ffmpeg 叠到成片上，带淡入淡出。

输入：
  CARDS      字幕卡文件。每张卡 = 起始秒、结束秒、文字（文字以剧本为准，时间用 retime_subs.py 在修好的音轨上测）。
             .tsv/.txt：每行  起始<TAB>结束<TAB>文字，# 开头是注释；
             .yaml/.json：列表（或 cards: 列表），每项 [起, 止, 文字] 或 {start, end, text}。
             示例见 examples/gemini-revenge/data/subs.example.tsv。
  IN.mp4     成片（画面和音轨都不动：画面重编码 crf 16，音轨直接复制）
输出：OUT.mp4（会丢掉嵌入的封面流，封面在字幕之后再嵌：scripts/embed_cover.sh）

样式（按 1536×864 写，其他分辨率按画面高度等比缩放）：字号 34、汉字间距 3、文字底边离画面底 64、
暖白 (242,240,235)、阴影高斯 5 px 75% 黑、细暗边 55%；每张卡前后各淡入淡出 0.12 s。
字体不内置，也没有系统路径默认值：在 config.yaml 的 fonts.zh（和 fonts.zh_index，.ttc 字体集要序号）里填，或用 --font。

用法示例：
  python3 scripts/render_subs.py cards.tsv film.mp4 film_subs.mp4
  python3 scripts/render_subs.py cards.tsv film.mp4 --preview auto --preview-dir /tmp/subs_pv   # 先看样式，不渲染整片
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, font_spec, load_config  # noqa: E402

REF_H = 864                      # 样式参数对应的参考画面高度
FILL = (242, 240, 235, 255)      # 暖白，不用纯白
EDGE = (10, 10, 10, 255)


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", "replace")[-500:] if isinstance(e.stderr, bytes) else ""
        sys.exit(f"命令失败（{cmd[0]}，退出码 {e.returncode}）：{err}")


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else []) + ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


def _num(v):
    return None if v in (None, "", "-") else float(v)


def load_cards(path, need_times=True):
    """读字幕卡，返回 [(起, 止, 文字)]；need_times=False 时起止可以是 None（只有文字的剧本行）。"""
    ext = os.path.splitext(path)[1].lower()
    rows = []
    if ext in (".yaml", ".yml", ".json"):
        try:
            import yaml
        except ImportError:
            sys.exit("缺少 PyYAML：pip install pyyaml")
        data = yaml.safe_load(open(path, encoding="utf-8"))
        data = data.get("cards", []) if isinstance(data, dict) else data
        for it in data or []:
            if isinstance(it, dict):
                rows.append((_num(it.get("start")), _num(it.get("end")), str(it["text"])))
            elif isinstance(it, str):
                rows.append((None, None, it))
            else:
                rows.append((_num(it[0]), _num(it[1]), str(it[2])))
    else:
        for ln in open(path, encoding="utf-8"):
            ln = ln.rstrip("\n").rstrip("\r")
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            parts = ln.split("\t")
            if len(parts) >= 3:
                rows.append((_num(parts[0]), _num(parts[1]), "\t".join(parts[2:]).strip()))
            else:
                rows.append((None, None, ln.strip()))
    if need_times:
        bad = [i + 1 for i, (s, e, _) in enumerate(rows) if s is None or e is None or e <= s]
        if bad:
            sys.exit(f"这些卡片缺起止时间或终点不晚于起点（按文件里的顺序数第几张）：{bad[:10]}。先用 retime_subs.py 测时间。")
    if not rows:
        sys.exit(f"字幕卡文件里没有内容：{path}")
    return rows


def timed(cards, lead=0.08, tail=0.30, gap=0.12, min_dur=0.9, film_end=None):
    """每张卡在测出的时间上稍作修饰，让观众读得完：提前 lead 出现、延后 tail 消失、至少显示 min_dur，
    且不压到下一张（留 gap）、不超过片尾。"""
    cards = sorted(cards, key=lambda c: c[0])
    out = []
    for i, (s, e, t) in enumerate(cards):
        s2 = max(0.0, s - lead)
        e2 = max(e + tail, s2 + min_dur)
        if i + 1 < len(cards):
            e2 = min(e2, cards[i + 1][0] - lead - gap)
        if film_end:
            e2 = min(e2, film_end)
        out.append((round(s2, 3), round(e2, 3), t))
    return out


class Style:
    def __init__(self, font, index, H, size=34, track=3, bottom=64):
        k = H / REF_H
        self.k = k
        self.size = max(8, round(size * k))
        self.track = track * k
        self.bottom = round(bottom * k)
        self.font = ImageFont.truetype(font, self.size, index=index)


def card_image(text, st, W, H):
    """画一张字幕卡，返回 (RGBA 图, 叠加的 x, y)。"""
    f, size, track = st.font, st.size, st.track
    cjk = lambda c: "\u3400" <= c <= "\u9fff" or c in "，。！？、：；"
    # 字间距只加在汉字之间；—— / …… 内部和英文单词内部不加
    gaps = [track if (cjk(a) or cjk(b)) and not (a in "—…" and b in "—…") and a != " " and b != " " else 0
            for a, b in zip(text, text[1:])] + [0]
    widths = [f.getlength(ch) for ch in text]
    tw = int(sum(widths) + sum(gaps))
    pad = round(24 * st.k)
    cw, ch = tw + 2 * pad, size + 2 * pad

    def draw(fill, img):
        d = ImageDraw.Draw(img)
        x = pad
        for c, w, g in zip(text, widths, gaps):
            d.text((x, pad - size * 0.12), c, font=f, fill=fill)
            x += w + g

    mask = Image.new("L", (cw, ch), 0)
    draw(255, mask)
    dx, dy = round(2 * st.k), round(3 * st.k)
    soft = mask.filter(ImageFilter.GaussianBlur(5 * st.k)).point(lambda v: int(v * 0.75))       # 柔和阴影
    edge = mask.filter(ImageFilter.MaxFilter(2 * round(st.k) + 1 if st.k >= 1.5 else 3)).point(lambda v: int(v * 0.55))  # 细暗边：白光闪过时字不会消失
    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    out.paste((0, 0, 0, 255), (dx, dy), soft.crop((0, 0, cw - dx, ch - dy)))
    out.paste(EDGE, (0, 0), edge)
    txt = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    draw(FILL, txt)
    out.alpha_composite(txt)
    return out, (W - cw) // 2, H - st.bottom - size - pad


def build(cards, st, src, out, W, H, fps, fade, work):
    ins, ch, last = [], [], "0:v"
    for k, (s, e, t) in enumerate(cards, 1):
        im, x, y = card_image(t, st, W, H)
        p = os.path.join(work, f"card_{k:03d}.png")
        im.save(p)
        d = e - s
        fd = min(fade, d / 4)
        ins += ["-loop", "1", "-framerate", f"{fps:g}", "-t", f"{d:.3f}", "-i", p]
        ch.append(f"[{k}:v]format=rgba,fade=in:st=0:d={fd:.3f}:alpha=1,fade=out:st={d - fd:.3f}:d={fd:.3f}:alpha=1,setpts=PTS+{s}/TB[s{k}]")
        ch.append(f"[{last}][s{k}]overlay={x}:{y}:eof_action=pass[o{k}]")
        last = f"o{k}"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", src] + ins + ["-filter_complex", ";".join(ch), "-map", f"[{last}]", "-map", "0:a?",
           "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out]
    run(cmd, stderr=subprocess.PIPE)
    print("OK", out, len(cards), "张字幕卡")


def pick_preview(cards):
    """自动挑几张有代表性的卡：最长的一行、含英文的、含 …… 的、含 —— 的、第一张，各取中点时间。"""
    picks = [("最长一行", max(cards, key=lambda c: len(c[2])))]
    for name, pred in (("含英文", lambda t: re.search(r"[A-Za-z]", t)), ("含……", lambda t: "……" in t), ("含——", lambda t: "——" in t)):
        c = next((c for c in cards if pred(c[2])), None)
        if c:
            picks.append((name, c))
    picks.append(("第一张", cards[0]))
    seen, out = set(), []
    for name, c in picks:
        if c[0] not in seen:
            seen.add(c[0])
            out.append((name, (c[0] + c[1]) / 2))
    return out


def main():
    ap = argparse.ArgumentParser(description="电影感对白字幕：透明 PNG 卡片 + ffmpeg overlay", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="预览要挑：白光闪过的帧、最长的一行、含英文的行、含 …… 的行（--preview auto 自动挑后四类里的前几张）。")
    ap.add_argument("cards", help="字幕卡文件（tsv/yaml）")
    ap.add_argument("src", help="成片 IN.mp4")
    ap.add_argument("out", nargs="?", help="输出 OUT.mp4（--preview 时可省）")
    ap.add_argument("--preview", help="只合成这几个时间点的静帧看效果，逗号分隔的秒数；或写 auto 自动挑")
    ap.add_argument("--preview-dir", default="subs_preview", help="预览图输出目录（默认 ./subs_preview）")
    ap.add_argument("--font", help="中文字体文件（默认 config 的 fonts.zh）")
    ap.add_argument("--font-index", type=int, help=".ttc 字体集里的序号（默认 config 的 fonts.zh_index，没有则 0）")
    ap.add_argument("--size", type=float, default=34, help="字号 px，按 1536×864 写（默认 34）")
    ap.add_argument("--track", type=float, default=3, help="汉字之间的间距 px（默认 3）")
    ap.add_argument("--bottom", type=float, default=64, help="文字底边离画面底边 px（默认 64；歌词块在它上方 128）")
    ap.add_argument("--fade", type=float, default=0.12, help="淡入淡出秒数（默认 0.12，卡片很短时取时长的 1/4）")
    ap.add_argument("--lead", type=float, default=0.08, help="提前出现秒数（默认 0.08）")
    ap.add_argument("--tail", type=float, default=0.30, help="延后消失秒数（默认 0.30）")
    ap.add_argument("--gap", type=float, default=0.12, help="与下一张之间至少留的秒数（默认 0.12）")
    ap.add_argument("--min-dur", type=float, default=0.9, help="最短显示秒数（默认 0.9）")
    ap.add_argument("--no-pad", action="store_true", help="不做 提前/延后/最短 修饰，严格按文件里的时间")
    ap.add_argument("--work-dir", help="放中间 PNG 的目录（默认临时目录，用完删除）")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    if not a.preview and not a.out:
        ap.error("需要 OUT.mp4（或者用 --preview 只看预览）")
    if not os.path.isfile(a.src):
        sys.exit(f"找不到成片：{a.src}")

    W, H = (int(x) for x in probe(a.src, "stream=width,height", "v:0").split(",")[:2])
    fps = eval_fps(probe(a.src, "stream=avg_frame_rate", "v:0"))
    dur = float(probe(a.src, "format=duration"))
    fpath, findex = font_spec(cfg, "zh", a.font, a.font_index)
    st = Style(fpath, findex, H, a.size, a.track, a.bottom)

    cards = load_cards(a.cards)
    cards = sorted(cards, key=lambda c: c[0])
    cards = [(s, e, t) for s, e, t in cards] if a.no_pad else timed(cards, a.lead, a.tail, a.gap, a.min_dur, dur)
    over = [i + 1 for i, (s, e, t) in enumerate(cards) if s >= dur]
    if over:
        sys.exit(f"有字幕卡的起点在片尾之后（片长 {dur:.2f} s）：第 {over[:10]} 张")

    if a.preview:
        os.makedirs(a.preview_dir, exist_ok=True)
        times = [("", float(t)) for t in a.preview.split(",")] if a.preview != "auto" else pick_preview(cards)
        with tempfile.TemporaryDirectory() as tmp:
            for name, t in times:
                hit = [c for c in cards if c[0] <= t <= c[1]]
                if not hit:
                    print(f"  {t:.2f} s：这个时刻没有字幕卡，跳过")
                    continue
                fr = os.path.join(tmp, "f.png")
                run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", a.src, "-frames:v", "1", fr])
                im = Image.open(fr).convert("RGBA")
                c, x, y = card_image(hit[0][2], st, W, H)
                im.alpha_composite(c, (x, y))
                p = os.path.join(a.preview_dir, f"subs_pv_{t:.2f}.jpg")
                im.convert("RGB").save(p, quality=92)
                print(f"  {t:.2f} s {name}：{p}")
        print("预览完成")
        return

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.work_dir:
        os.makedirs(a.work_dir, exist_ok=True)
        build(cards, st, a.src, a.out, W, H, fps, a.fade, a.work_dir)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            build(cards, st, a.src, a.out, W, H, fps, a.fade, tmp)


def eval_fps(s):
    n, _, d = s.partition("/")
    return float(n) / float(d or 1)


if __name__ == "__main__":
    main()

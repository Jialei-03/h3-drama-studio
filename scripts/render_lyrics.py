#!/usr/bin/env python3
"""歌词字幕：读用户提供的、有授权的歌词文件，按"第几对 → 原曲起止秒"的时间表换算成片中时间，
画成电影感双语字幕（英文斜体在上、中文在下，位于对白字幕正上方），叠到成片的配乐段上。

红线（lyrics.md 第 1 节）：
  - 只读用户提供的歌词文件；不由 AI 听写、不由 AI 翻译（中文行也来自用户的文件）。
  - **本脚本绝不打印歌词**：终端只有"几对、几句、片中起止时间"，没有任何歌词文字。改脚本时保持这一点。
  - 时间表里只存"第几对"和秒数，不存歌词文字（带文字的时间表本身就是一份歌词副本）。
  - 歌词文件、含歌词的成片都不要放进仓库。

输入：
  LYRICS.txt   UTF-8 文本，去掉空行后英文一行、中文一行交替（--zh-first 则中文在前）；行数必须成对
  TIMES        时间表：第几对（从 1 起，空行不算）→ 原曲起止秒，秒数可写 90.5 或 1:30.5。
               .tsv：每行 对号<TAB>起<TAB>终（# 注释；多余的列忽略）；.yaml：pairs: {1: [起, 终], ...}。
               没有歌声的间奏不填，那几对会被跳过。示例见 examples/gemini-revenge/data/lyrics_times.example.tsv
  IN.mp4       已加好配乐的成片（画面重编码 crf 16；音轨和嵌入的封面流直接复制）
  偏移与范围   片中时间 = 原曲时间 + OFF。--offset OFF 直接给；或 --bgm-plan mix_bgm 用的 yaml（自动算 OFF 和音乐范围，
               并带上 shifts，这样剪片后只改一处）。--range 起,止 覆盖音乐在片中的范围。
输出：OUT.mp4；终端打印汇总和每句的片中起止时间。

每张卡的时间（单位秒；a、b = 这一对在原曲的起止，a_next = 下一对有时间表的起点）：
  s = a + OFF - lead(0.1)；e = min(max(b + OFF + tail(0.3), s + min_dur(1.0)), a_next + OFF - gap(0.12), s + max_dur(7.5))
  只保留落在音乐范围内的；第一句不早于范围起点后 0.3 s；淡入淡出各 0.25 s。

字体：不内置，也没有系统路径默认值。config.yaml 的 fonts.en_italic（英文斜体衬线）、fonts.zh（中文）必填，
fonts.symbol（画 ♪ 用的带符号字形的字体）可选，没配就用 fonts.zh 画 ♪（显示成方框就配 fonts.symbol，或加 --no-note 不画 ♪）。

用法示例：
  python3 scripts/render_lyrics.py lyrics.txt times.tsv film_bgm.mp4 film_lyrics.mp4 --offset -27.4 --range 80.7,161.6
  python3 scripts/render_lyrics.py lyrics.txt times.tsv film_bgm.mp4 --bgm-plan bgm.yaml --preview
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, font_spec, get, load_config  # noqa: E402

REF_H = 864
FILL = (242, 240, 235, 255)
EDGE = (10, 10, 10, 255)


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ffmpeg/ffprobe 失败（退出码 {e.returncode}）")   # 不回显 stderr，以免把滤镜里的内容带出来


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else []) + ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


def tsec(v):
    """90.5 / '90.5' / '1:30.5' → 秒"""
    if isinstance(v, (int, float)):
        return float(v)
    parts = str(v).strip().split(":")
    return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))


def read_times(path):
    """返回 {第几对: (起, 终)}"""
    ext = os.path.splitext(path)[1].lower()
    out = {}
    if ext in (".yaml", ".yml", ".json"):
        import yaml
        d = yaml.safe_load(open(path, encoding="utf-8")) or {}
        d = d.get("pairs", d) if isinstance(d, dict) else d
        items = d.items() if isinstance(d, dict) else [(x[0], x[1:3]) for x in d]
        for k, v in items:
            out[int(k)] = (tsec(v[0]), tsec(v[1]))
    else:
        for ln in open(path, encoding="utf-8"):
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            c = ln.rstrip("\n").split("\t")
            try:
                out[int(c[0])] = (tsec(c[1]), tsec(c[2]))
            except (ValueError, IndexError):
                sys.exit(f"时间表格式不对：每行应是 对号<TAB>起<TAB>终（出错的是第 {len(out) + 1} 条附近）")
    if not out:
        sys.exit("时间表是空的")
    return out


def read_pairs(path, zh_first=False):
    """歌词文件：非空行，英中交替。只返回行内容，不打印。"""
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
    if len(lines) % 2:
        sys.exit(f"歌词文件去掉空行后有 {len(lines)} 行，不成对（应该英文一行、中文一行交替）")
    pairs = [(lines[i], lines[i + 1]) for i in range(0, len(lines), 2)]
    return [(zh, en) for en, zh in pairs] if zh_first else pairs


def plan_offset(plan_path, track, film_dur=None):
    """从 mix_bgm 的 yaml 算 OFF 和音乐在片中的范围（都已按 shifts 平移）。"""
    import yaml
    P = yaml.safe_load(open(plan_path, encoding="utf-8")) or {}
    shifts = P.get("shifts") or []
    sh = lambda t: t + sum(float(s["delta"]) for s in shifts if t >= float(s["at"]))
    tr = (P.get("tracks") or [])[track]
    off = sh(float(tr["align"]["film_time"])) - float(tr["align"]["song_time"])
    lo = sh(float(tr["fade_in"][0]))
    if tr.get("fade_out"):
        hi = sh(float(tr["fade_out"][1]))
    else:                                         # 一直放到歌曲结束：用歌曲长度推出片中的结束时刻
        f = os.path.expanduser(str(tr.get("file") or ""))
        f = f if os.path.isabs(f) else os.path.join(os.path.dirname(os.path.abspath(plan_path)), f)
        if not os.path.isfile(f):
            sys.exit("--bgm-plan 里没有 fade_out，又找不到歌曲文件来推结束时刻：请加 --range 起,止")
        hi = lo + (float(probe(f, "format=duration")) - (lo - off))
    return off, lo, hi


class Fonts:
    def __init__(self, en, zh, note, H, show_note=True):
        self.k = H / REF_H
        k = self.k
        self.en_size, self.zh_size = round(30 * k), round(34 * k)
        self.note_en_size, self.note_zh_size = round(26 * k), round(29 * k)
        self.EN = ImageFont.truetype(en[0], self.en_size, index=en[1])
        self.ZH = ImageFont.truetype(zh[0], self.zh_size, index=zh[1])
        self.NE = ImageFont.truetype(note[0], self.note_en_size, index=note[1])
        self.NZ = ImageFont.truetype(note[0], self.note_zh_size, index=note[1])
        self.show_note = show_note


def card(en, zh, F, W, H, bottom=128):
    """画一张双语歌词卡，返回 (RGBA, x, y)。每行句前加 ♪（用带符号字形的字体画，文字字体不变）。"""
    k = F.k
    pad, gap, track = round(26 * k), round(9 * k), 3 * k
    ne = (F.NE.getlength("♪") + gap) if F.show_note else 0
    nz = (F.NZ.getlength("♪") + gap) if F.show_note else 0
    ew = ne + F.EN.getlength(en)
    zw = nz + F.ZH.getlength(zh) + track * max(0, len(zh) - 1)
    cw = int(max(ew, zw)) + 2 * pad
    chh = F.en_size + round(10 * k) + F.zh_size + 2 * pad

    def draw(fill, img):
        d = ImageDraw.Draw(img)
        x = (cw - ew) / 2
        if F.show_note:
            d.text((x, pad + 2 * k), "♪", font=F.NE, fill=fill)
        d.text((x + ne, pad - 4 * k), en, font=F.EN, fill=fill)
        x = (cw - zw) / 2
        y = pad + F.en_size + round(10 * k) - 4 * k
        if F.show_note:
            d.text((x, y + 5 * k), "♪", font=F.NZ, fill=fill)
        x += nz
        for c in zh:
            d.text((x, y), c, font=F.ZH, fill=fill)
            x += F.ZH.getlength(c) + track

    m = Image.new("L", (cw, chh), 0)
    draw(255, m)
    dx, dy = round(2 * k), round(3 * k)
    out = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    out.paste((0, 0, 0, 255), (dx, dy), m.filter(ImageFilter.GaussianBlur(6 * k)).point(lambda v: int(v * 0.9)).crop((0, 0, cw - dx, chh - dy)))
    out.paste(EDGE, (0, 0), m.filter(ImageFilter.MaxFilter(3)).point(lambda v: int(v * 0.7)))
    txt = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
    draw(FILL, txt)
    out.alpha_composite(txt)
    return out, (W - cw) // 2, H - round(bottom * k) - chh + pad


def make_cards(pairs, times, off, lo, hi, lead, tail, min_dur, gap, max_dur, edge):
    """按公式把"第几对 → 原曲起止"换成片中的 (起, 止, 第几对)。返回卡片列表和每对是否有时间表。"""
    keys = sorted(times)
    bad = [k for k in keys if not 1 <= k <= len(pairs)]
    if bad:
        sys.exit(f"时间表里有超出歌词范围的对号（歌词共 {len(pairs)} 对）：{bad[:10]}")
    cards = []
    for idx, k in enumerate(keys):
        a, b = times[k]
        s = a + off - lead
        nxt = times[keys[idx + 1]][0] + off - gap if idx + 1 < len(keys) else 1e9
        e = min(max(b + off + tail, s + min_dur), nxt, s + max_dur)
        if e <= lo or s >= hi:
            continue
        cards.append((max(s, lo + edge), min(e, hi), k))
    return cards


def main():
    ap = argparse.ArgumentParser(description="歌词字幕（读授权歌词文件，不打印歌词）", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="验收：开头、中间、结尾各听一对，歌词比歌声略早出现、不晚；和对白字幕同时出现时不重叠；搜一遍日志和聊天，确认没有歌词文字。")
    ap.add_argument("lyrics", help="歌词文件 LYRICS.txt（用户提供、有授权）")
    ap.add_argument("times", help="时间表（tsv/yaml）：第几对 → 原曲起止秒")
    ap.add_argument("src", help="成片 IN.mp4（已含配乐）")
    ap.add_argument("out", nargs="?", help="输出 OUT.mp4（--preview 时可省）")
    ap.add_argument("--offset", type=float, help="OFF：片中时间 = 原曲时间 + OFF（和 mix_bgm 里 film_time - song_time 是同一个数，含剪片平移）")
    ap.add_argument("--bgm-plan", help="mix_bgm 用的 yaml：自动算 OFF 和音乐范围")
    ap.add_argument("--track", type=int, default=0, help="--bgm-plan 里用第几条 track（从 0 起，默认 0）")
    ap.add_argument("--range", help="音乐在片中的范围 起,止（秒）；歌词只出现在这个范围内")
    ap.add_argument("--zh-first", action="store_true", help="歌词文件里中文在前、英文在后")
    ap.add_argument("--preview", action="store_true", help="只合成前几句的静帧看样式，不渲染整片")
    ap.add_argument("--preview-dir", default="lyrics_preview")
    ap.add_argument("--en-font", help="英文斜体字体文件（默认 config 的 fonts.en_italic）")
    ap.add_argument("--en-font-index", type=int)
    ap.add_argument("--font", help="中文字体文件（默认 config 的 fonts.zh）")
    ap.add_argument("--font-index", type=int)
    ap.add_argument("--symbol-font", help="画 ♪ 的字体（默认 config 的 fonts.symbol，没有就用中文字体）")
    ap.add_argument("--symbol-font-index", type=int)
    ap.add_argument("--no-note", action="store_true", help="不在行首画 ♪")
    ap.add_argument("--bottom", type=float, default=128, help="歌词块底边离画面底边 px（默认 128，对白字幕是 64），按 1536×864 写")
    ap.add_argument("--lead", type=float, default=0.1, help="比歌声提前出现的秒数（默认 0.1）")
    ap.add_argument("--tail", type=float, default=0.3, help="歌声结束后多留的秒数（默认 0.3）")
    ap.add_argument("--min-dur", type=float, default=1.0)
    ap.add_argument("--max-dur", type=float, default=7.5)
    ap.add_argument("--gap", type=float, default=0.12, help="与下一对之间至少留的秒数（默认 0.12）")
    ap.add_argument("--edge", type=float, default=0.3, help="第一句不早于音乐范围起点后多少秒（默认 0.3）")
    ap.add_argument("--verbose", action="store_true", help="渲染失败排查用：显示 ffmpeg 的报错输出（滤镜图里只有位置和图片名，没有歌词文字）")
    ap.add_argument("--fade", type=float, default=0.25, help="淡入淡出秒数（默认 0.25，卡片很短时取时长的 1/4）")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    if not a.preview and not a.out:
        ap.error("需要 OUT.mp4（或者用 --preview 只看样式）")
    for p in (a.lyrics, a.times, a.src):
        if not os.path.isfile(p):
            sys.exit(f"找不到文件：{p}")

    off = lo = hi = None
    if a.bgm_plan:
        off, lo, hi = plan_offset(a.bgm_plan, a.track)
    if a.offset is not None:
        off = a.offset
    if a.range:
        lo, hi = (float(x) for x in a.range.split(","))
    if off is None or lo is None or hi is None:
        sys.exit("需要偏移和音乐范围：用 --bgm-plan，或同时给 --offset 和 --range")

    W, H = (int(x) for x in probe(a.src, "stream=width,height", "v:0").split(",")[:2])
    n_, _, d_ = probe(a.src, "stream=avg_frame_rate", "v:0").partition("/")
    fps = float(n_) / float(d_ or 1)
    zh = font_spec(cfg, "zh", a.font, a.font_index)
    en = font_spec(cfg, "en_italic", a.en_font, a.en_font_index, "歌词的英文行要用斜体衬线字体。")
    sym = a.symbol_font or get(cfg, "fonts.symbol")
    note = font_spec(cfg, "symbol", a.symbol_font, a.symbol_font_index) if sym else zh
    F = Fonts(en, zh, note, H, show_note=not a.no_note)

    pairs = read_pairs(a.lyrics, a.zh_first)
    times = read_times(a.times)
    cards = make_cards(pairs, times, off, lo, hi, a.lead, a.tail, a.min_dur, a.gap, a.max_dur, a.edge)
    # 只打印数字：没有歌词文字
    print(f"歌词 {len(pairs)} 对，时间表给了 {len(times)} 对，落在片中音乐范围（{lo:.1f}–{hi:.1f} s）内 {len(cards)} 句；OFF={off:+.3f}")
    print("片中时间：", " ".join(f"{s:.1f}-{e:.1f}" for s, e, _ in cards))
    if not cards:
        sys.exit("没有任何一句落在音乐范围内：检查 --offset、--range 和时间表")

    if a.preview:
        os.makedirs(a.preview_dir, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            for s, e, k in cards[:3]:
                t = (s + e) / 2
                fr = os.path.join(tmp, "f.png")
                run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", a.src, "-frames:v", "1", fr])
                im = Image.open(fr).convert("RGBA")
                c, x, y = card(pairs[k - 1][0], pairs[k - 1][1], F, W, H, a.bottom)
                im.alpha_composite(c, (x, y))
                p = os.path.join(a.preview_dir, f"lyrics_pv_{t:.1f}.jpg")
                im.convert("RGB").save(p, quality=90)
                print("  预览", p)
        print("预览完成")
        return

    with tempfile.TemporaryDirectory() as tmp:
        ins, ch, last = [], [], "0:v:0"
        for i, (s, e, k) in enumerate(cards, 1):
            im, x, y = card(pairs[k - 1][0], pairs[k - 1][1], F, W, H, a.bottom)
            p = os.path.join(tmp, f"{i:02d}.png")
            im.save(p)
            d = e - s
            fd = min(a.fade, d / 4)
            ins += ["-loop", "1", "-framerate", f"{fps:g}", "-t", f"{d:.3f}", "-i", p]
            ch.append(f"[{i}:v]format=rgba,fade=in:st=0:d={fd:.3f}:alpha=1,fade=out:st={d - fd:.3f}:d={fd:.3f}:alpha=1,setpts=PTS+{s}/TB[s{i}]")
            ch.append(f"[{last}][s{i}]overlay={x}:{y}:eof_action=pass[o{i}]")
            last = f"o{i}"
        nvid = len([x for x in probe(a.src, "stream=index", "v").splitlines() if x.strip()])
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", a.src] + ins + ["-filter_complex", ";".join(ch), "-map", f"[{last}]", "-map", "0:a:0"]
        if nvid >= 2:                                               # 带着嵌入的封面流，直接复制
            cmd += ["-map", "0:v:1"]
        cmd += ["-c:v:0", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p"]
        if nvid >= 2:
            cmd += ["-c:v:1", "copy", "-disposition:v:1", "attached_pic"]
        cmd += ["-c:a", "copy", "-movflags", "+faststart", a.out]
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        run(cmd, stderr=None if a.verbose else subprocess.DEVNULL)
    print("OK", a.out, len(cards), "句")


if __name__ == "__main__":
    main()

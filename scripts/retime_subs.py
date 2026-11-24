#!/usr/bin/env python3
"""给字幕卡测时间：对成片的音轨做逐词识别，把剧本里的每句台词对到识别出来的词上，给出每句的起止时间建议。

规则：字幕文字以**剧本**为准，识别只用来测时间；识别听错人名、漏字没关系，对不上的句子会标出来让你用耳朵定。
必须在**重建过音轨**之后的成片上测（见 splice.md），否则越往后越晚。

对法：剧本和识别结果都切成"单位"（每个汉字一个单位，每个英文/数字词一个单位），用最长公共子序列
（difflib）做顺序对齐；没对上的单位（人名听错、漏字）在相邻的对上的单位之间按位置插值。
每句：起点 = 第一个字的开始，终点 = 最后一个字的结束；匹配率 = 对上的字数 / 这句的字数。
  匹配率 >= 0.8 标 OK；介于 --min-match 和 0.8 之间标"低匹配"（请听一遍）；低于 --min-match 标"没对上"，
  不给新时间、保留旧时间。给出的是原始语音时间，不含"提前出现/延后消失"的修饰（那是 render_subs.py 做的）。

另一个用法：只平移（--shift），不跑识别。剪片之后剪点之后的卡片整体前移：--shift 41.7:-0.25（从 41.7 s 起往前 0.25 s）。

输入：
  SCRIPT   剧本台词。字幕卡文件（tsv/yaml，起止可以缺省或是旧的），或每行一句的纯文本
  SOURCE   成片（或音轨）；用 --words 直接给逐词时间时可省略
输出：-o 新字幕卡（.tsv 或 .yaml，格式同 render_subs.py 的输入）；终端打印新旧时间对照表。

逐词识别：默认用 mlx-whisper（Apple 芯片，pip install mlx-whisper），没有就用 openai-whisper（pip install openai-whisper）；
两个都没装会给出提示。也可以用别的工具自己出逐词时间，存成 JSON 列表 [[词, 起, 止], ...]，用 --words 读入。

用法示例：
  python3 scripts/retime_subs.py script.tsv film.mp4 -o cards.tsv --words-cache film.words.json
  python3 scripts/retime_subs.py cards.tsv --shift 41.7:-0.25 --shift 63.3:-0.5833 -o cards_shifted.tsv
"""
import argparse
import json
import os
import re
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, load_config  # noqa: E402
from render_subs import load_cards  # noqa: E402

UNIT = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]|[a-z0-9]+(?:'[a-z]+)?")


def units(text):
    return UNIT.findall(text.lower().replace("’", "'"))


def make_shift(shifts):
    """shifts=[(cut, delta)]：时间 >= cut 的统一加 delta（delta 为负就是往前挪）。"""
    return lambda t: None if t is None else t + sum(d for c, d in shifts if t >= c)


# ---------------------------------------------------------------- 逐词识别
def transcribe(source, backend, model, language, prompt):
    """返回 [(词, 起, 止)]。mlx-whisper 优先，其次 openai-whisper；都没有就报错并提示安装。"""
    kw = dict(language=language, word_timestamps=True, condition_on_previous_text=False)
    if prompt:
        kw["initial_prompt"] = prompt
    res = None
    if backend in ("auto", "mlx"):
        try:
            import mlx_whisper
            res = mlx_whisper.transcribe(source, path_or_hf_repo=model or "mlx-community/whisper-large-v3-turbo", **kw)
        except ImportError:
            if backend == "mlx":
                sys.exit("没装 mlx-whisper：pip install mlx-whisper（需要 Apple 芯片）")
    if res is None and backend in ("auto", "whisper"):
        try:
            import whisper
            res = whisper.load_model(model or "turbo").transcribe(source, **kw)
        except ImportError:
            pass
    if res is None:
        sys.exit("没有可用的语音识别：请安装 mlx-whisper（Apple 芯片）或 openai-whisper，"
                 "或者用别的工具出逐词时间，存成 JSON 列表 [[词, 起, 止], ...] 后用 --words 读入")
    return [(w["word"], float(w["start"]), float(w["end"])) for s in res["segments"] for w in s.get("words", [])]


def load_words(path):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for w in data:
        out.append((w["word"], float(w["start"]), float(w["end"])) if isinstance(w, dict) else (w[0], float(w[1]), float(w[2])))
    return out


# ---------------------------------------------------------------- 对齐
def fix_stretched(words, max_per_unit=1.5):
    """Whisper 的逐词时间有个常见毛病：一句话前面如果是很长的静音/音乐/打斗，第一个词的开始会被拖回上一句的结尾
    （例：一个字被标成 8 秒长）。结束时间通常还准，所以对每字超过 max_per_unit 秒的词，按"典型字时长"从结束往回推起点。
    返回 (修正后的词表, 被修正的个数)。[启发式，只在作者的一部片上试过]"""
    per = sorted((e - s) / max(1, len(units(w))) for w, s, e in words if units(w))
    ok = [p for p in per if p <= max_per_unit]
    typ = ok[len(ok) // 2] if ok else 0.25
    out, n = [], 0
    for w, s, e in words:
        k = max(1, len(units(w)))
        if (e - s) / k > max_per_unit:
            s, n = e - typ * k, n + 1
        out.append((w, s, e))
    return out, n


def align(lines, words, min_match=0.5, min_block=2):
    """lines = [文字]；words = [(词, 起, 止)]。返回每句的 dict(start, end, ratio, flag)。"""
    su, spans = [], []
    for t in lines:
        u = units(t)
        spans.append((len(su), len(su) + len(u)))
        su += u
    au, at0, at1 = [], [], []
    for w, s, e in words:
        us = units(w)
        for k, u in enumerate(us):                       # 一个识别词里有多个字：在词的时间里平分
            au.append(u)
            at0.append(s + (e - s) * k / len(us))
            at1.append(s + (e - s) * (k + 1) / len(us))
    if not su or not au:
        return [dict(start=None, end=None, ratio=0.0, flag="无可对字" if not su else "没对上") for _ in lines]

    line_of = {}
    for li, (a, b) in enumerate(spans):
        for j in range(a, b):
            line_of[j] = li
    match = [None] * len(su)
    for i, j, n in SequenceMatcher(None, su, au, autojunk=False).get_matching_blocks():
        if n < min_block:
            # 单个字的零星匹配多半是巧合（的、了、我）；只有这个块正好就是一整句（短句）才留
            li = line_of.get(i)
            if li is None or spans[li][1] - spans[li][0] > n:
                continue
        for k in range(n):
            match[i + k] = j + k

    # 没对上的字：同一句里前后都有对上的字 -> 在它们之间按位置插值；只有一侧 -> 从那一侧按"中位字时长"外推。
    # 不跨句插值：句间常有很长的停顿（打戏、过场），跨句插值会把整句拖歪。整句都没对上的句子，才用前后句的位置粗估，并标"没对上"。
    mi = [j for j in range(len(su)) if match[j] is not None]
    durs = sorted(at1[match[j]] - at0[match[j]] for j in mi)
    md = durs[len(durs) // 2] if durs else 0.25
    ts, te = [0.0] * len(su), [0.0] * len(su)
    for j in mi:
        ts[j], te[j] = at0[match[j]], at1[match[j]]
    for (a0, b0) in spans:
        inside = [j for j in range(a0, b0) if match[j] is not None]
        for j in range(a0, b0):
            if match[j] is not None:
                continue
            if inside:
                p = next((x for x in reversed(inside) if x < j), None)
                q = next((x for x in inside if x > j), None)
            else:                                   # 整句没对上：借前后句最近的对上的字
                p = next((x for x in range(a0 - 1, -1, -1) if match[x] is not None), None)
                q = next((x for x in range(b0, len(su)) if match[x] is not None), None)
            if p is not None and q is not None:
                g0, g1 = te[p], max(ts[q], te[p])
                cnt = sum(1 for x in range(p + 1, q) if match[x] is None)
                r = sum(1 for x in range(p + 1, j + 1) if match[x] is None)
                ts[j], te[j] = g0 + (g1 - g0) * (r - 1) / cnt, g0 + (g1 - g0) * r / cnt
            elif q is not None:
                ts[j] = ts[q] - (q - j) * md
                te[j] = ts[j] + md
            elif p is not None:
                ts[j] = te[p] + (j - p - 1) * md
                te[j] = ts[j] + md
            else:
                ts[j], te[j] = 0.0, md

    out = []
    for a, b in spans:
        if b == a:
            out.append(dict(start=None, end=None, ratio=0.0, flag="无可对字"))
            continue
        ratio = sum(match[j] is not None for j in range(a, b)) / (b - a)
        flag = "OK" if ratio >= 0.8 else ("低匹配" if ratio >= min_match else "没对上")
        out.append(dict(start=round(max(0.0, ts[a]), 2), end=round(max(te[b - 1], ts[a] + 0.2), 2), ratio=ratio, flag=flag))
    return out


# ---------------------------------------------------------------- 输出
def write_cards(path, rows):
    ext = os.path.splitext(path)[1].lower()
    fmt = lambda v: "" if v is None else f"{v:.2f}"
    if ext in (".yaml", ".yml"):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 字幕卡：[起始秒, 结束秒, 文字]。retime_subs.py 生成，请用耳朵抽查后再用。\ncards:\n")
            for s, e, t in rows:
                f.write(f"  - [{fmt(s) or 'null'}, {fmt(e) or 'null'}, {json.dumps(t, ensure_ascii=False)}]\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 起始秒\t结束秒\t文字（retime_subs.py 生成，请用耳朵抽查后再用）\n")
            for s, e, t in rows:
                f.write(f"{fmt(s)}\t{fmt(e)}\t{t}\n")


def main():
    ap = argparse.ArgumentParser(description="用逐词识别给字幕卡测起止时间（建议值），或整体平移字幕时间", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="抽查：开头、中间、结尾各听一处，字幕出现的时刻对着嘴型；标了 低匹配/没对上 的句子逐句听。")
    ap.add_argument("script", help="剧本台词（字幕卡 tsv/yaml，或每行一句的纯文本）")
    ap.add_argument("source", nargs="?", help="成片或音轨（用 --words 或只做 --shift 时可省）")
    ap.add_argument("-o", "--output", help="写出新字幕卡（.tsv 或 .yaml）")
    ap.add_argument("--words", help="已有的逐词时间 JSON（[[词, 起, 止], ...]），跳过识别")
    ap.add_argument("--words-cache", help="识别结果缓存：文件存在就读，不存在就识别后写入（长片省时间）")
    ap.add_argument("--backend", choices=["auto", "mlx", "whisper"], default="auto", help="识别后端（默认 auto：mlx-whisper 优先）")
    ap.add_argument("--model", help="模型（mlx 默认 mlx-community/whisper-large-v3-turbo；openai-whisper 默认 turbo）")
    ap.add_argument("--language", default="zh", help="语言（默认 zh）")
    ap.add_argument("--prompt", help="识别的 initial_prompt；默认取剧本前 --prompt-chars 个字，对专有名词有帮助")
    ap.add_argument("--no-prompt", action="store_true", help="不给 initial_prompt")
    ap.add_argument("--prompt-chars", type=int, default=200)
    ap.add_argument("--min-match", type=float, default=0.5, help="匹配率低于它的句子标'没对上'、不给新时间（默认 0.5；"
                    "作者的整片转写里要求至少对上六成字）")
    ap.add_argument("--min-block", type=int, default=2, help="短于它的零星匹配不算（默认 2），整句就这么短的除外")
    ap.add_argument("--stretch", type=float, default=1.5, help="每个字超过这么多秒的词，视为起点被拖长，按典型字时长从结束往回推（默认 1.5）")
    ap.add_argument("--no-fix-stretch", action="store_true", help="不做上面的修正，原样使用识别给的词时间")
    ap.add_argument("--shift", action="append", metavar="起点:增量",
                    help="从起点秒起整体平移增量秒（负数前移），可重复；例 41.7:-0.25。作用在文件里已有的旧时间上")
    add_config_arg(ap)
    a = ap.parse_args()
    load_config(a.config)

    rows = load_cards(a.script, need_times=False)
    shifts = []
    for s in a.shift or []:
        c, _, d = s.rpartition(":")
        shifts.append((float(c), float(d)))
    sh = make_shift(shifts)
    old = [(sh(s), sh(e), t) for s, e, t in rows]

    if not a.source and not a.words and not a.words_cache:
        if not shifts:
            ap.error("没有 SOURCE 也没有 --words：要么给成片跑识别，要么用 --shift 只做平移")
        res = [dict(start=s, end=e, ratio=1.0, flag="平移") for s, e, _ in old]
    else:
        if a.words:
            words = load_words(a.words)
        elif a.words_cache and os.path.isfile(a.words_cache):
            words = load_words(a.words_cache)
            print(f"读入缓存的逐词时间：{a.words_cache}（{len(words)} 个词）")
        else:
            if not a.source or not os.path.isfile(a.source):
                sys.exit(f"找不到成片：{a.source}")
            prompt = None if a.no_prompt else (a.prompt or "".join(t for _, _, t in rows)[:a.prompt_chars])
            print("逐词识别中……（长片要几十秒到几分钟）")
            words = transcribe(a.source, a.backend, a.model, a.language, prompt)
            if a.words_cache:
                json.dump(words, open(a.words_cache, "w", encoding="utf-8"), ensure_ascii=False)
        if not a.no_fix_stretch:
            words, nfix = fix_stretched(words, a.stretch)
            if nfix:
                print(f"修正了 {nfix} 个被拉长的词（Whisper 常把长静音后的第一个字的起点拖回上一句结尾）")
        print(f"识别出 {len(words)} 个词")
        res = align([t for _, _, t in rows], words, a.min_match, a.min_block)

    new_rows = []
    print(f"{'#':>3} {'旧起':>7} {'新起':>7} {'Δ':>6} {'旧止':>7} {'新止':>7} {'Δ':>6} {'匹配':>5} {'标记':<6} 文字")
    f = lambda v: "-" if v is None else f"{v:.2f}"
    d = lambda n, o: "-" if n is None or o is None else f"{n - o:+.2f}"
    for i, ((os_, oe, t), r) in enumerate(zip(old, res), 1):
        ok = r["flag"] in ("OK", "低匹配", "平移")
        ns, ne = (r["start"], r["end"]) if ok else (os_, oe)       # 没对上的句子保留旧时间，让人去听
        new_rows.append((ns, ne, t))
        print(f"{i:>3} {f(os_):>7} {f(ns):>7} {d(ns, os_):>6} {f(oe):>7} {f(ne):>7} {d(ne, oe):>6} {r['ratio']:>5.0%} {r['flag']:<6} {t}")
    bad = [i for i, r in enumerate(res, 1) if r["flag"] in ("低匹配", "没对上", "无可对字")]
    print(f"\n共 {len(res)} 句，OK {sum(r['flag'] in ('OK', '平移') for r in res)} 句；需要听一遍的：{bad if bad else '无'}")
    if a.output:
        write_cards(a.output, new_rows)
        print("已写出", a.output)


if __name__ == "__main__":
    main()

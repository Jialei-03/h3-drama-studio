#!/usr/bin/env python3
"""给视频听写台词，并按剧本台词定出每句实际说话的时间点。验片（review_ep.py）和对字幕时间（见 drama-postproduction）都用它。

输入：一个或多个视频/音频文件；可选 --lines：剧本台词文件（一行一句，UTF-8）。
输出：
  - 不给 --lines：打印听写出的分句和时间；
  - 给了 --lines：再打印每句剧本台词的起止秒（按字数从逐词时间戳里依次取够；听写字数不到应有字数的 60% 就标“没对上”，不硬对）。
  --json 把结果写成 json（segments、words、lines）。听写结果按文件名缓存在 --cache 目录，同一个文件不重复转写。
依赖（可选，缺哪个都会给出清楚的报错）：mlx-whisper（Apple 芯片，默认优先）或 openai-whisper；另需 ffmpeg 在 PATH 里。

用法示例：
  python3 scripts/asr.py clip.mp4
  python3 scripts/asr.py clip.mp4 --lines lines.txt --lang zh --json clip_asr.json

注意：同音字会听错（例：把一个英文名字听成发音相近的汉字），“没对上”不等于念错，以耳朵为准；
英文台词（例：招牌大招名）用中文模式听不准，不会参与比对。
状态：mlx-whisper 后端在本机用真实片段验证过；openai-whisper 后端未验证。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
OPENAI_MODEL = "turbo"
ZH_PROMPT = "以下是普通话的句子。"


def norm(s):
    """去掉标点和空白，只留汉字、字母、数字：按字数对台词时用。"""
    return re.sub(r"[^\w]", "", s).replace("_", "")


def _backend(name):
    if name in ("auto", "mlx"):
        try:
            import mlx_whisper  # noqa: F401
            return "mlx"
        except ImportError:
            if name == "mlx":
                sys.exit("没有安装 mlx-whisper：pip install mlx-whisper（需要 Apple 芯片）")
    if name in ("auto", "openai"):
        try:
            import whisper  # noqa: F401
            return "openai"
        except ImportError:
            if name == "openai":
                sys.exit("没有安装 openai-whisper：pip install openai-whisper")
    sys.exit("听写需要 mlx-whisper（Apple 芯片）或 openai-whisper，请先安装其中一个：\n  pip install mlx-whisper\n  pip install openai-whisper\n"
             "没有它们也能用 review_ep.py --no-asr 只做切点检测和截帧。")


def transcribe(clip, lang="zh", backend="auto", model=None, prompt=None, cache=None, offline=False):
    """返回 {"segments": [[start, end, text]], "words": [[word, start, end]]}；结果按文件名缓存。"""
    clip = Path(clip)
    be = _backend(backend)
    model = model or (MLX_MODEL if be == "mlx" else OPENAI_MODEL)
    cf = None
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        tag = re.sub(r"[^\w.-]", "_", f"{be}_{model}_{lang}")
        ph = hashlib.md5((prompt or "").encode("utf-8")).hexdigest()[:6] if prompt else "0"  # 提示词不同，听写结果可能不同
        cf = Path(cache) / f"{clip.stem}.{tag}.{ph}.json"
        if cf.exists():
            return json.loads(cf.read_text(encoding="utf-8"))
    if offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")  # 模型已下载时跳过联网检查，网络不好时更稳
    kw = dict(language=lang, word_timestamps=True, initial_prompt=prompt or (ZH_PROMPT if lang == "zh" else None),
              condition_on_previous_text=False)  # 不让上一句带偏下一句；压缩比阈值防止复读式幻觉
    if be == "mlx":
        import mlx_whisper
        r = mlx_whisper.transcribe(str(clip), path_or_hf_repo=model, compression_ratio_threshold=2.0, **kw)
    else:
        import whisper
        r = whisper.load_model(model).transcribe(str(clip), compression_ratio_threshold=2.0, **kw)
    out = {"segments": [[round(s["start"], 2), round(s["end"], 2), s["text"]] for s in r["segments"]],
           "words": [[w["word"], w["start"], w["end"]] for s in r["segments"] for w in s.get("words", [])]}
    if cf:
        cf.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def line_times(words, lines, min_share=0.6):
    """每句剧本台词在片子里实际说话的 (起, 止) 秒；听写字数不到应有字数的 min_share 就整体返回 None（不硬对）。"""
    w = [(norm(t), s, e) for t, s, e in words if norm(t)]
    need = [len(norm(l)) for l in lines]
    if not need or sum(len(t) for t, _, _ in w) < min_share * sum(need):
        return [None] * len(lines)
    out, k = [], 0
    for n in need:
        got, st, en = 0, None, None
        while k < len(w) and got < n:
            t, s, e = w[k]
            st = s if st is None else st
            en = e
            got += len(t)
            k += 1
        out.append((st, en) if st is not None else None)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", help="视频或音频文件")
    ap.add_argument("--lines", help="剧本台词文件，一行一句")
    ap.add_argument("--lang", default="zh", help="语言代码，默认 zh")
    ap.add_argument("--backend", choices=["auto", "mlx", "openai"], default="auto")
    ap.add_argument("--model", help=f"模型；默认 mlx: {MLX_MODEL}，openai-whisper: {OPENAI_MODEL}")
    ap.add_argument("--cache", default="asr_cache", help="听写缓存目录（默认 ./asr_cache）；--cache '' 关闭缓存")
    ap.add_argument("--offline", action="store_true", help="设 HF_HUB_OFFLINE=1：模型已在本地时不联网")
    ap.add_argument("--json", help="把结果写成 json（多个文件时每个文件一条）")
    a = ap.parse_args()
    lines = [l.strip() for l in Path(a.lines).read_text(encoding="utf-8").splitlines() if l.strip()] if a.lines else []
    results = {}
    for c in a.clips:
        if not Path(c).is_file():
            sys.exit(f"文件不存在：{c}")
        r = transcribe(c, a.lang, a.backend, a.model, "".join(lines) or None, a.cache or None, a.offline)
        print(f"== {c}")
        for s, e, t in r["segments"]:
            print(f"  [{s:6.2f}-{e:6.2f}] {t.strip()}")
        if lines:
            lt = line_times(r["words"], lines)
            r["lines"] = [{"line": l, "start": (x[0] if x else None), "end": (x[1] if x else None)} for l, x in zip(lines, lt)]
            if lt[0] is None and not any(lt):
                print("  [没对上] 听写字数不到剧本台词应有字数的 60%，不硬对；请手工听时间")
            for l, x in zip(lines, lt):
                print(f"  {'%6.2f-%6.2f' % x if x else '   没对上   '}  {l}")
        results[str(c)] = r
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写 {a.json}")


if __name__ == "__main__":
    main()

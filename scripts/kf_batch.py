#!/usr/bin/env python3
"""按一份 yaml 清单并发批量出图（定妆图、场景图、召唤物图、受损阶段场景图、封面底图……）。

输入：出图清单 yaml（写法见 examples/gemini-revenge/data/keyframes.example.yaml）。清单里有：
  - refs：参考图库，名字 -> 文件，可带一句"定义"（{p} 会换成 image N）和提示词里用的称呼；
  - jobs：每张图一条，写 id、用哪些参考图、提示词（可以用 {名字} 引用参考图库里的称呼）；
  - prefix / keep / suffix：每张图都加的风格段、"保持原样"句、收尾句（可空）。
输出：<out_dir>/<id>_<tag>.png；每张图实际发出的提示词存到 <out_dir>/prompts/；已存在的图默认跳过。
出图通过 scripts/relay_img.py 的接口（地址和密钥来自环境变量，见 config.yaml 的 image_api）。

用法示例：
  python3 scripts/kf_batch.py keyframes.yaml --tag r1 --workers 4 --only arena,hero
  python3 scripts/kf_batch.py keyframes.yaml --dry-run          # 只打印每张图的完整提示词和参考图，不联网

状态：本机用 --dry-run 验证了清单解析和提示词拼装；未在干净环境对真实服务做端到端验证。
"""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import add_config_arg, get, load_config  # noqa: E402
import relay_img  # noqa: E402


def load_manifest(path):
    try:
        import yaml
    except ImportError:
        sys.exit("缺少 PyYAML：pip install pyyaml")
    m = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(m.get("jobs"), list) or not m["jobs"]:
        sys.exit("清单里没有 jobs 列表")
    return m


def _p(base, f):
    """清单里的相对路径相对于清单文件所在目录。"""
    f = Path(str(f)).expanduser()
    return f if f.is_absolute() else base / f


def assemble(job, m):
    """按清单拼出一张图的完整提示词，返回 (prompt, [参考图路径])。

    顺序：prefix（风格段）／各参考图的定义句 + keep 句 + world（有场景类参考图时）／提示词正文 + 参考图的 append 句 + suffix。
    为什么把定义句放在提示词里：参考图只按"第几张"传给接口，要在文字里说明第几张是谁，模型才知道各管什么。"""
    base = Path(m["_base"])
    lib = m.get("refs") or {}
    names, defs, files, appends, scene = {}, [], [], [], False
    for i, r in enumerate(job.get("refs") or [], 1):
        ent = lib.get(r)
        if ent is None:  # 直接写文件路径也行：没有定义句，也没有称呼
            files.append(_p(base, r))
            continue
        files.append(_p(base, ent["file"]))
        names[r] = ent.get("name", r)
        if ent.get("define"):
            defs.append(ent["define"].replace("{p}", f"image {len(files)}").strip())
        if ent.get("append"):
            appends.append(ent["append"].strip())
        scene = scene or bool(ent.get("scene"))
    text = str(job.get("prompt", "")).strip()
    for k, v in names.items():
        text = text.replace("{" + k + "}", v)
    left = re.findall(r"\{[^{}]*\}", text)
    if left:  # 写错名字或没把它列进本条的 refs：不替换就发出去会让模型照字面画
        raise ValueError(f"{job['id']}: 提示词里有没解析的占位符 {left}（只能引用本条 refs 里的名字）")
    head = " ".join(defs + ([str(m["keep"]).strip()] if m.get("keep") and defs else []) + ([str(m["world"]).strip()] if scene and m.get("world") else []))
    tail = " ".join(x for x in [text] + appends + ([str(m["suffix"]).strip()] if m.get("suffix") else []) if x)
    prompt = "\n\n".join(x for x in [str(m.get("prefix", "")).strip(), head, tail] if x)
    return prompt, files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", help="出图清单 yaml")
    ap.add_argument("--tag", default="r1", help="输出文件名后缀，每轮换一个（r1、r2……），不覆盖旧图")
    ap.add_argument("--only", help="只出这几条，逗号分隔的 id")
    ap.add_argument("--workers", type=int, help="并发张数；默认读清单的 workers，再没有就用 4")
    ap.add_argument("--size", help="宽x高；默认读清单的 size，再读 image_api.size，再没有 1536x1024")
    ap.add_argument("--model", help="模型名；默认读清单的 model，再读 image_api.model")
    ap.add_argument("--out-dir", help="输出目录；默认读清单的 out_dir（相对清单文件），再没有就是清单所在目录下的 out/")
    ap.add_argument("--force", action="store_true", help="目标文件已存在也重出")
    ap.add_argument("--dry-run", action="store_true", help="只打印拼好的提示词和参考图，不联网、不写文件")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    m = load_manifest(a.manifest)
    m["_base"] = str(Path(a.manifest).resolve().parent)
    base = Path(m["_base"])
    out_dir = Path(a.out_dir) if a.out_dir else _p(base, m.get("out_dir", "out"))
    model = a.model or m.get("model") or get(cfg, "image_api.model")
    size = a.size or m.get("size") or get(cfg, "image_api.size", "1536x1024")
    workers = a.workers or int(m.get("workers", 4))
    retries = int(m.get("retries", 1))
    base_env = get(cfg, "image_api.base_url_env", "IMAGE_API_BASE")
    key_env = get(cfg, "image_api.key_env", "IMAGE_API_KEY")
    only = set(a.only.split(",")) if a.only else None
    ids = [j["id"] for j in m["jobs"]]
    if len(set(ids)) != len(ids):
        sys.exit("清单里有重复的 id")
    if only and (missing := only - set(ids)):
        sys.exit(f"--only 里有清单没有的 id：{sorted(missing)}")

    todo = []
    for j in m["jobs"]:
        if only and j["id"] not in only:
            continue
        try:
            prompt, files = assemble(j, m)
        except ValueError as e:
            sys.exit(str(e))
        for f in files:
            if not f.is_file():
                print(f"[警告] {j['id']}: 参考图不存在 {f}" + ("（dry-run 继续）" if a.dry_run else ""), file=sys.stderr)
                if not a.dry_run:
                    sys.exit(1)
        out = out_dir / f"{j['id']}_{a.tag}.png"
        if out.exists() and not a.force:
            print(f"跳过 {out.name}（已存在，--force 可重出）")
            continue
        todo.append((j, prompt, files, out, j.get("size") or size))

    if a.dry_run:
        for j, prompt, files, out, sz in todo:
            print(f"\n=== {j['id']} -> {out}  size={sz}  model={model or '<未指定>'}")
            print("参考图：" + (" | ".join(f"image {i}={f.name}{'' if f.is_file() else '(不存在)'}" for i, f in enumerate(files, 1)) or "无（走文生图）"))
            print(prompt)
        print(f"\n[dry-run] {len(todo)} 张待出，并发 {workers}，失败重试 {retries} 次；环境变量 {base_env}/{key_env} 在真实运行时读取")
        return
    if not model:
        sys.exit("没有指定模型：清单里写 model、用 --model，或在 config.yaml 的 image_api.model 里填。")
    (out_dir / "prompts").mkdir(parents=True, exist_ok=True)

    def go(item):
        j, prompt, files, out, sz = item
        (out_dir / "prompts" / f"{j['id']}_{a.tag}.txt").write_text(prompt, encoding="utf-8")
        err = ""
        for _ in range(retries + 1):  # 偶发失败（超时、限流）重试一次就够，同一个错出第二次要看提示词
            try:
                secs, n = relay_img.generate(out, prompt, [str(f) for f in files], model, sz, base_env, key_env)
                return f"{out.name} ok {secs}s {n} bytes"
            except RuntimeError as e:
                err = str(e)
        return f"{out.name} 失败：{err[:300]}"

    with ThreadPoolExecutor(workers) as ex:
        for line in ex.map(go, todo):
            print(line, flush=True)


if __name__ == "__main__":
    main()

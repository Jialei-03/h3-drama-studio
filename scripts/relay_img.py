#!/usr/bin/env python3
"""用兼容 OpenAI 图像接口的服务出一张图：不带参考图走 /v1/images/generations，带参考图走 /v1/images/edits。

输入：输出文件、提示词文件（纯文本）、0 到多张参考图。
输出：一张图（接口返回 b64 或 url 都能处理）。
地址、密钥、模型都不写在命令行里：
  - 地址和密钥只从环境变量读，变量名在 config.yaml 的 image_api.base_url_env / key_env（默认 IMAGE_API_BASE / IMAGE_API_KEY）；
  - 地址写到主机名为止，不带 /v1（带了也行，脚本会处理）；
  - 模型默认取 image_api.model，也可以用 --model 指定。

用法示例：
  export IMAGE_API_BASE=https://你的服务地址  IMAGE_API_KEY=你的密钥
  python3 scripts/relay_img.py out.png prompt.txt ref_char.png ref_scene.png --size 1536x1024
  python3 scripts/relay_img.py out.png prompt.txt ref.png --dry-run     # 只打印将要发送的内容，不联网、不读密钥

状态：本机用 --dry-run 验证了数据流；未在干净环境对真实服务做端到端验证。
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import add_config_arg, get, load_config  # noqa: E402


def _endpoint(base, has_refs):
    base = base.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base + ("/v1/images/edits" if has_refs else "/v1/images/generations")


def build_request(model, prompt, size, refs):
    """返回 (path_suffix_is_edit, body_bytes, content_type)。带参考图用 multipart，字段 image[]；否则 JSON。"""
    if not refs:
        return json.dumps({"model": model, "prompt": prompt, "size": size, "n": 1}).encode(), "application/json"
    b = uuid.uuid4().hex

    def field(n, v):
        return f'--{b}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode()

    body = field("model", model) + field("prompt", prompt) + field("size", size) + field("n", "1")
    for i, rp in enumerate(refs):
        body += (f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="ref{i}.png"\r\n'
                 f'Content-Type: image/png\r\n\r\n').encode() + Path(rp).read_bytes() + b"\r\n"
    body += f"--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"


def generate(out, prompt, refs, model, size, base_env, key_env, timeout=600):
    """出一张图并写到 out。成功返回 (耗时秒, 字节数)；失败抛 RuntimeError（信息里不含密钥）。"""
    base, key = os.environ.get(base_env), os.environ.get(key_env)
    if not base or not key:
        raise RuntimeError(f"环境变量 {base_env} / {key_env} 没有设置（变量名可在 config.yaml 的 image_api 里改）")
    body, ctype = build_request(model, prompt, size, refs)
    req = urllib.request.Request(_endpoint(base, bool(refs)), data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": ctype})
    t0 = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {e.read().decode(errors='replace')[:500]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"连接失败：{e.reason}")
    d = r["data"][0]
    data = base64.b64decode(d["b64_json"]) if d.get("b64_json") else urllib.request.urlopen(d["url"], timeout=120).read()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(data)
    return round(time.time() - t0), len(data)


def describe(out, prompt, refs, model, size, base_env, key_env):
    """--dry-run 的输出：不联网，不读密钥的值，只说在不在。"""
    base = os.environ.get(base_env)
    print(f"[dry-run] endpoint : {_endpoint(base, bool(refs)) if base else f'<环境变量 {base_env} 未设置>'}")
    print(f"[dry-run] key env  : {key_env} = {'已设置' if os.environ.get(key_env) else '未设置'}（值不会打印）")
    print(f"[dry-run] model    : {model or '<未指定：请用 --model 或填 config.yaml 的 image_api.model>'}")
    print(f"[dry-run] size     : {size}    output: {out}")
    print(f"[dry-run] prompt   : {len(prompt)} 字符，开头：{prompt[:80]!r}")
    print(f"[dry-run] 请求格式 : {'multipart/form-data，字段 model/prompt/size/n + image[] x%d' % len(refs) if refs else 'application/json {model,prompt,size,n}'}")
    for r in refs:
        print(f"[dry-run]   ref   : {r}  ({Path(r).stat().st_size} bytes)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="输出图片路径")
    ap.add_argument("prompt_file", help="提示词文件（UTF-8 纯文本）")
    ap.add_argument("refs", nargs="*", help="参考图（0 到多张，按顺序即提示词里的 image 1、image 2……）")
    ap.add_argument("--model", help="模型名；默认读 config.yaml 的 image_api.model")
    ap.add_argument("--size", help="宽x高，默认读 image_api.size，再没有就用 1536x1024")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true", help="只打印将要发送的内容，不联网")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    base_env = get(cfg, "image_api.base_url_env", "IMAGE_API_BASE")
    key_env = get(cfg, "image_api.key_env", "IMAGE_API_KEY")
    model = a.model or get(cfg, "image_api.model")
    size = a.size or get(cfg, "image_api.size", "1536x1024")
    p = Path(a.prompt_file)
    if not p.is_file():
        sys.exit(f"提示词文件不存在：{p}")
    for r in a.refs:
        if not Path(r).is_file():
            sys.exit(f"参考图不存在：{r}")
    prompt = p.read_text(encoding="utf-8")
    if a.dry_run:
        describe(a.out, prompt, a.refs, model, size, base_env, key_env)
        return
    if not model:
        sys.exit("没有指定模型：用 --model，或在 config.yaml 的 image_api.model 里填。")
    try:
        secs, n = generate(a.out, prompt, a.refs, model, size, base_env, key_env, a.timeout)
    except RuntimeError as e:
        print(model, "失败：", e, file=sys.stderr)
        sys.exit(1)
    print(model, "ok", secs, "s", n, "bytes")


if __name__ == "__main__":
    main()

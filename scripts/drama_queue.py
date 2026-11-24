#!/usr/bin/env python3
"""出片队列：按 shots.json 一段接一段往 ComfyUI 提交任务，写 results.json；运行在出片主机上。

重点：默认用仓库自带的 workflows/h3_base.api.json，config.example.yaml 里的映射表已经和它对好。
想用自己的工作流：在 ComfyUI 里用"导出 (API)"得到 json，在 config.yaml 的 workflow: 里填 json 路径和"角色 → 节点编号/输入名"的映射表。脚本按映射表改写节点：
  - 改值：模型文件名、提示词、宽高帧数、种子、采样器、sigma、参考图、保存前缀；
  - 自动加节点：LoRA 链、SigmaShift、首尾帧/接续锚点（MiniMaxH3AddGuide）、专属二采（潜空间放大+重新加噪+后半段采样）、一采单独存视频。
哪些要你的工作流里已经有、哪些由脚本加、限制在哪，见 skills/h3-video/references/queue.md 的"接入你自己的工作流"一节。

子命令：
  run        跑队列（每轮重读 shots.json；目录里出现 STOP 文件就在当前段结束后退出）。加 --dry-run 只生成并打印将提交的工作流 json，不联网
  check-map  对照导出的 json 检查映射表：节点在不在、类型对不对、连线是否符合脚本的假设
  submit     把 build_shots.py 出的一轮 shots 合并进总 shots.json（可用 scp 传到主机）

用法示例：
  python3 scripts/drama_queue.py check-map
  python3 scripts/drama_queue.py run --dry-run --shots shots.json --only f1_t1 --save-dir /tmp/graphs
  python3 scripts/drama_queue.py run                       # 在主机上，读 config.yaml 的 host.queue_dir
  python3 scripts/drama_queue.py submit round.json --master shots.json --upload

状态：用仓库自带的 workflows/h3_base.api.json 做 dry-run，生成的工作流和作者主机当时实际提交的两份（一段文戏、一段带接续的武戏）
      逐节点一致（结构和参数都相同）；但这个重写版脚本本身还没有真的向 ComfyUI 提交过任务。
配方出处：专属二采来自吃猪侠233，上下文接续来自惊尘（见 skills/h3-video/references/credits.md）。
"""
import argparse
import copy
import json
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import add_config_arg, get, load_config  # noqa: E402

NEW = "q_"  # 脚本新加节点的编号前缀：不会和 ComfyUI 导出的数字编号冲突

# 映射表里每个角色：默认的输入名、通常的节点类型（check-map 用来提醒）
ROLES = {
    "unet":         {"input": "unet_name",       "classes": ["UNETLoader"],                 "what": "扩散主模型加载器"},
    "clip":         {"input": "clip_name",       "classes": ["CLIPLoader"],                 "what": "文本编码器加载器"},
    "prompt":       {"input": "prompt",          "classes": ["MiniMaxH3ReferenceToVideo"],  "what": "正向提示词（参考生视频的条件节点）"},
    "width":        {"input": "width",           "classes": ["MiniMaxH3ReferenceToVideo"],  "what": "一采宽"},
    "height":       {"input": "height",          "classes": ["MiniMaxH3ReferenceToVideo"],  "what": "一采高"},
    "length":       {"input": "length",          "classes": ["MiniMaxH3ReferenceToVideo"],  "what": "帧数"},
    "ref_size":     {"input": "ref_image_size",  "classes": ["MiniMaxH3ReferenceToVideo"],  "what": "参考图尺寸策略 match/max"},
    "ref_images":   {"prefix": "ref_images.ref_image_", "classes": ["MiniMaxH3ReferenceToVideo"], "what": "参考图输入（节点 + 输入名前缀）"},
    "seed":         {"input": "noise_seed",      "classes": ["RandomNoise"],                "what": "种子"},
    "sampler":      {"input": "sampler_name",    "classes": ["KSamplerSelect"],             "what": "一采采样器"},
    "sigmas":       {"input": "sigmas",          "classes": ["ManualSigmas"],               "what": "一采 sigma 曲线（手写字符串）"},
    "model_in":     {"input": "model",           "classes": None,                           "what": "LoRA 链/SigmaShift 的出口：这个输入会被接到链尾"},
    "cond":         {"classes": ["MiniMaxH3ReferenceToVideo"],                              "what": "条件节点：输出0=正向条件，输出1=空潜空间"},
    "guider":       {"classes": ["BasicGuider"],                                            "what": "引导节点（CFG 1）"},
    "pass1":        {"classes": ["SamplerCustomAdvanced"],                                  "what": "一采采样节点：输出1=去噪后的音画联合潜空间"},
    "video_vae":    {"classes": ["VAELoader"],                                              "what": "视频 VAE（锚点、一采预览解码用）"},
    "audio_vae":    {"classes": ["VAELoader"],                                              "what": "音频 VAE（接续的音频锚点、一采预览解码用）"},
    "decode_video": {"input": "samples",         "classes": ["VAEDecode"],                  "what": "视频解码：samples 要直接接 pass1 的输出1"},
    "decode_audio": {"input": "samples",         "classes": ["VAEDecodeAudio"],             "what": "音频解码：samples 要直接接 pass1 的输出1"},
    "save":         {"input": "filename_prefix", "classes": ["SaveVideo"],                  "what": "保存节点"},
}
# 每个功能需要哪些角色：缺了就在用到时报错，不用的功能不必配
NEEDS = {
    "基础": ["unet", "clip", "prompt", "width", "height", "length", "ref_images", "seed", "model_in", "cond", "guider", "save"],
    "首尾帧/接续锚点": ["cond", "video_vae"],
    "接续音频(ctx)": ["audio_vae"],
    "sched 调度器代替手写 sigma": ["sigmas"],
    "二采 up2": ["pass1", "decode_video", "decode_audio", "seed", "guider", "cond"],
    "一采另存视频 save_stage1": ["pass1", "video_vae", "audio_vae", "decode_video", "decode_audio", "save"],
    "dense（关稀疏注意力）": ["model_in", "guider"],
}
OLD_DEFAULT_NOTE = "没写的字段沿用你工作流里已有的值"


class MapError(Exception):
    pass


class Mapping:
    def __init__(self, cfg):
        self.nodes = get(cfg, "workflow.nodes", {}) or {}
        self.drop = [str(x) for x in (get(cfg, "workflow.drop_nodes", []) or [])]

    def has(self, role):
        return bool((self.nodes.get(role) or {}).get("node") not in (None, ""))

    def node(self, role):
        if not self.has(role):
            raise MapError(f"config.yaml 的 workflow.nodes.{role} 没有填（{ROLES[role]['what']}）")
        return str(self.nodes[role]["node"])

    def inp(self, role):
        r = ROLES[role]
        key = "prefix" if "prefix" in r else "input"
        return (self.nodes.get(role) or {}).get(key) or r[key]


# ---------------------------------------------------------------- 图改写
def frames_for(seconds, ctx_frames=0):
    """秒数换算成帧数，加上接续帧，向上取到 17k+5（H3 只接受这样的帧数）。"""
    fr = max(5, round(seconds * 24) + ctx_frames)
    return fr + (5 - fr % 17) % 17


class Assets:
    """接续/首尾帧锚点需要的素材：从已渲好的片子里截帧或截片段，放进 ComfyUI 的 input 目录。dry-run 时只打印将要做什么。"""

    def __init__(self, cfg, queue_dir, dry):
        self.dry, self.R = dry, Path(queue_dir) if queue_dir else None
        self.input = Path(get(cfg, "host.comfyui_input", "")) if get(cfg, "host.comfyui_input") else None
        self.ff = get(cfg, "host.ffmpeg", "ffmpeg")
        self.fps = float(get(cfg, "project.fps", 24))

    def _results(self):
        return json.loads((self.R / "results.json").read_text(encoding="utf-8"))

    def _need_input(self):
        if not self.input:
            raise MapError("用到了 @ 锚点或 ctx，需要 config.yaml 的 host.comfyui_input（主机上 ComfyUI 的 input 目录）")

    def ctx_clip(self, key, n):
        """上一段最后 n 帧和对应音频，截成一个短 mp4。"""
        name = f"ctx_{key}_{n}.mp4"
        if self.dry:
            print(f"[dry-run] 将用 ffmpeg 从 results.json 里 {key} 的成片截最后 {n} 帧（含音频）-> input/{name}")
            return name
        self._need_input()
        res = self._results()
        video = res[key]["video"]
        total = res[key].get("frames") or 241  # 主机上不一定有 ffprobe：队列在 results.json 里记了每段的帧数
        t0 = (total - n) / self.fps
        subprocess.check_output([self.ff, "-loglevel", "error", "-y", "-ss", f"{t0:.4f}", "-i", video, "-frames:v", str(n), "-t", f"{n / self.fps:.4f}",
                                 "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(self.input / name)])
        return name

    def anchor_from(self, key, slot):
        """'@id_tN' -> 做首帧锚点取上一段末尾最清晰的一帧，做尾帧锚点取开头第一帧；':end' / ':start' 可强制指定。"""
        pick = "end" if slot == "first" else "start"
        if ":" in key:
            key, pick = key.split(":")
        name = f"chain_{key}_{pick}.png"
        if self.dry:
            print(f"[dry-run] 将从 {key} 的成片取{'末尾 0.5 秒里最清晰的一帧' if pick == 'end' else '第一帧'} -> input/{name}")
            return name
        self._need_input()
        video = self._results()[key]["video"]
        if pick != "end":
            subprocess.check_output([self.ff, "-loglevel", "error", "-y", "-ss", "0", "-i", video, "-frames:v", "1", "-update", "1", str(self.input / name)])
            return name
        # 最后一帧常带运动模糊，模糊会带进下一段的开头（作者片中相邻两段的接缝翻车）：取最后 0.5 秒里最清晰的一帧
        import numpy as np
        from PIL import Image
        tmp = self.input / f"_tail_{key}"
        tmp.mkdir(exist_ok=True)
        for p in tmp.glob("*.png"):
            p.unlink()
        subprocess.check_output([self.ff, "-loglevel", "error", "-y", "-sseof", "-0.5", "-i", video, str(tmp / "%03d.png")])

        def sharp(p):
            a = np.asarray(Image.open(p).convert("L"), dtype=np.float32)
            return float((a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]).var())  # 拉普拉斯方差

        best = max(sorted(tmp.glob("*.png"))[-12:], key=sharp)
        (self.input / name).write_bytes(best.read_bytes())
        return name


def build_graph(base, M, s, cfg, assets):
    """按映射表把 shot 写进你导出的工作流，返回 (图, 帧数, 改动说明列表)。"""
    g = copy.deepcopy(base)
    notes = []
    for k in M.drop:
        if k not in g:
            raise MapError(f"workflow.drop_nodes 里的节点 {k} 不在导出的 json 里")
        g.pop(k)
    if M.drop:
        notes.append(f"删除节点 {', '.join(M.drop)}")

    def node(role):
        nid = M.node(role)
        if nid not in g:
            raise MapError(f"workflow.nodes.{role} 指向的节点 {nid} 不在导出的 json 里（被 drop_nodes 删了？）")
        return nid

    def put(role, value):
        nid, name = node(role), M.inp(role)
        if name not in g[nid]["inputs"]:
            raise MapError(f"节点 {nid}（{g[nid]['class_type']}）没有输入 {name!r}（workflow.nodes.{role}）；它现有的输入：{sorted(g[nid]['inputs'])}")
        g[nid]["inputs"][name] = value

    # --- 模型文件名：shot 里写了就用，否则用 config.models，再没有就沿用工作流里已有的 ---
    for role, field, cfgkey in (("unet", "unet", "models.unet"), ("clip", "clip", "models.text_encoder")):
        v = s.get(field) or get(cfg, cfgkey)
        if v:
            put(role, v)
    # --- 模型链：unet -> LoRA… -> SigmaShift -> model_in ---
    prev = [node("unet"), 0]
    for k, (name, w) in enumerate(s.get("loras", [])):
        g[f"{NEW}lora{k}"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": prev, "lora_name": name, "strength_model": w}}
        prev = [f"{NEW}lora{k}", 0]
    if s.get("shift"):  # [视频, 音频]：二采的 beta 调度要从带 shift 的模型算出
        g[f"{NEW}shift"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": prev, "shift_video": s["shift"][0], "shift_audio": s["shift"][1]}}
        prev = [f"{NEW}shift", 0]
    put("model_in", prev)
    sched_model = prev
    if s.get("loras") or s.get("shift"):
        notes.append(f"模型链：{len(s.get('loras', []))} 个 LoRA" + (f" + SigmaShift{s['shift']}" if s.get("shift") else "") + f" -> {M.node('model_in')}.{M.inp('model_in')}")
    # --- 采样参数 ---
    if s.get("sampler"):
        put("sampler", s["sampler"])
    if s.get("sigmas"):
        put("sigmas", s["sigmas"])
    put("seed", s["seed"])
    # --- 参考图 ---
    cn, prefix = node("ref_images"), M.inp("ref_images")
    root = prefix.split(".")[0] if "." in prefix else prefix
    for k in [k for k in g[cn]["inputs"] if k.startswith(root)]:
        g[cn]["inputs"].pop(k)
    for k, img in enumerate(s["images"]):
        g[f"{NEW}img{k}"] = {"class_type": "LoadImage", "inputs": {"image": img}}
        g[cn]["inputs"][f"{prefix}{k}"] = [f"{NEW}img{k}", 0]
    # --- 提示词、尺寸、帧数 ---
    ctx_n = s.get("ctx_frames", 22) if s.get("ctx") else 0  # 接续：上一段末尾 22 帧加音频放在新片开头，拼接时剪掉，所以要多渲这些帧
    fr = frames_for(s["seconds"], ctx_n)
    put("prompt", s["prompt"])
    if s.get("w"):
        put("width", s["w"])
    if s.get("h"):
        put("height", s["h"])
    put("length", fr)
    if s.get("ref_size"):
        put("ref_size", s["ref_size"])
    if s.get("sched"):  # 用调度器代替手写 sigma，例如 ["beta", 33]：原地替换 sigma 节点，下游连线不用改
        g[node("sigmas")] = {"class_type": "BasicScheduler", "inputs": {"model": sched_model, "scheduler": s["sched"][0], "steps": s["sched"][1], "denoise": 1.0}}
        notes.append(f"节点 {M.node('sigmas')} 换成 BasicScheduler {s['sched']}")
    # --- 首帧/尾帧/接续锚点：MiniMaxH3AddGuide 串在条件后面 ---
    cond, cnode, guides = [node("cond"), 0], node("cond"), []
    if s.get("ctx") and s.get("first"):
        raise MapError("first 和 ctx 都锚在第 0 帧，不能同时写")
    for slot, idx in (("first", 0), ("last", -1)):
        img = s.get(slot)
        if not img:
            continue
        if img.startswith("@"):
            img = assets.anchor_from(img[1:], slot)
        g[f"{NEW}a_{slot}"] = {"class_type": "LoadImage", "inputs": {"image": img}}
        g[f"{NEW}g_{slot}"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {"positive": cond, "latent": [cnode, 1], "frame_idx": idx,
                                                                               "vae": [node("video_vae"), 0], "image": [f"{NEW}a_{slot}", 0]}}
        cond = [f"{NEW}g_{slot}", 0]
        guides.append(slot)
    if s.get("ctx"):
        clip = assets.ctx_clip(s["ctx"].lstrip("@"), ctx_n)
        g[f"{NEW}c_lv"] = {"class_type": "LoadVideo", "inputs": {"file": clip}}
        g[f"{NEW}c_gvc"] = {"class_type": "GetVideoComponents", "inputs": {"video": [f"{NEW}c_lv", 0]}}
        extra = {"audio": [f"{NEW}c_gvc", 1], "audio_vae": [node("audio_vae"), 0]} if s.get("ctx_audio", True) else {}
        g[f"{NEW}g_ctx"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {"positive": cond, "latent": [cnode, 1], "frame_idx": 0,
                                                                            "vae": [node("video_vae"), 0], "image": [f"{NEW}c_gvc", 0], **extra}}
        cond = [f"{NEW}g_ctx", 0]
        guides.append("ctx")
    if guides:
        notes.append("锚点：" + "、".join(guides))
    gd = node("guider")
    g[gd]["inputs"]["conditioning"] = cond
    if s.get("dense"):  # 跳过稀疏注意力：引导节点的模型直接取 model_in 节点的输出，绕开它后面的补丁节点
        g[gd]["inputs"]["model"] = [node("model_in"), 0]
        notes.append("dense：引导节点绕开 model_in 之后的补丁")
    # --- 专属二采 up2：一采跑完整条曲线 -> 视频潜空间放大 -> 在放大后的潜空间上重新加噪 -> 只跑调度器后半段 ---
    u = s.get("up2")
    if u:
        for k in ("w", "h"):
            if u[k] % 32:
                raise MapError(f"up2.{k}={u[k]} 不是 32 的倍数（二采会报 shape 错误；1536×864 可以，1584×912 不行）")
        p1, nz = node("pass1"), node("seed")
        up_model = get(cfg, "models.latent_upscaler")
        if not up_model:
            raise MapError("up2 需要 config.yaml 的 models.latent_upscaler（潜空间放大模型文件名）")
        g[f"{NEW}sep"] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": [p1, 1]}}
        g[f"{NEW}upm"] = {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": up_model}}
        g[f"{NEW}up"] = {"class_type": "MiniMaxH3LatentUpscaleWithModel", "inputs": {"model": [f"{NEW}upm", 0], "samples": [f"{NEW}sep", 0], "width": u["w"], "height": u["h"]}}
        g[f"{NEW}cat"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": [f"{NEW}up", 0], "audio_latent": [f"{NEW}sep", 1]}}  # 音频潜变量原样保留
        g[f"{NEW}sch2"] = {"class_type": "BasicScheduler", "inputs": {"model": sched_model, "scheduler": u["sched"][0], "steps": u["sched"][1], "denoise": 1.0}}
        g[f"{NEW}split2"] = {"class_type": "SplitSigmas", "inputs": {"sigmas": [f"{NEW}sch2", 0], "step": u["split"]}}
        g[f"{NEW}smp2"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": u.get("sampler", "euler")}}
        guider2 = [gd, 0]
        if guides:  # 锚点是按一采潜空间的尺寸写进条件的：放大后不重加会报 shape mismatch，所以另建一个 guider
            cond2 = [node("cond"), 0]
            for slot in ("first", "last", "ctx"):
                if slot not in guides:
                    continue
                g[f"{NEW}g2_{slot}"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {**g[f"{NEW}g_{slot}"]["inputs"], "positive": cond2, "latent": [f"{NEW}cat", 0]}}
                cond2 = [f"{NEW}g2_{slot}", 0]
            g[f"{NEW}guider2"] = copy.deepcopy(g[gd])
            g[f"{NEW}guider2"]["inputs"]["conditioning"] = cond2
            guider2 = [f"{NEW}guider2", 0]
        # 噪声用与一采同一个节点（同一个种子）；sigmas 取后半段，第一个值就是重新加噪的噪声水平
        g[f"{NEW}s2"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": [nz, 0], "guider": guider2, "sampler": [f"{NEW}smp2", 0],
                                                                         "sigmas": [f"{NEW}split2", 1], "latent_image": [f"{NEW}cat", 0]}}
        if s.get("save_stage1"):  # 一采结果另存成 <id>_t<take>_stage1：克隆你自己的 解码 -> CreateVideo -> 保存 三个节点，保证编码设置一致
            _clone_stage1(g, M, node, p1, f"{s['id']}_t{s.get('take', 1)}_stage1", get(cfg, "host.output_subdir", "h3_drama"))
        put_decode = lambda role: g[node(role)]["inputs"].__setitem__(M.inp(role), [f"{NEW}s2", 1])
        put_decode("decode_video")
        put_decode("decode_audio")
        notes.append(f"二采 up2：{u['w']}x{u['h']}，{u['sched']}，第 {u['split']} 步切开，{u.get('sampler', 'euler')}；解码节点改接二采输出")
    elif s.get("save_stage1"):
        raise MapError("save_stage1 只在有 up2 的 shot 上有意义")
    key = f"{s['id']}_t{s.get('take', 1)}"
    put("save", f"{get(cfg, 'host.output_subdir', 'h3_drama')}/{key}")
    return g, fr, notes


def _clone_stage1(g, M, node, pass1, prefix_key, subdir):
    save = node("save")
    cv = g[save]["inputs"].get("video")
    if not (isinstance(cv, list) and cv[0] in g and {"images", "audio"} <= set(g[cv[0]]["inputs"])):
        raise MapError("save_stage1 需要 save 节点的 video 输入接在一个带 images/audio 输入的节点（CreateVideo）上")
    g[f"{NEW}p1v"] = copy.deepcopy(g[node("decode_video")]); g[f"{NEW}p1v"]["inputs"][M.inp("decode_video")] = [pass1, 1]
    g[f"{NEW}p1a"] = copy.deepcopy(g[node("decode_audio")]); g[f"{NEW}p1a"]["inputs"][M.inp("decode_audio")] = [pass1, 1]
    g[f"{NEW}p1c"] = copy.deepcopy(g[cv[0]]); g[f"{NEW}p1c"]["inputs"].update(images=[f"{NEW}p1v", 0], audio=[f"{NEW}p1a", 0])
    g[f"{NEW}p1s"] = copy.deepcopy(g[save]); g[f"{NEW}p1s"]["inputs"].update(video=[f"{NEW}p1c", 0], **{M.inp("save"): f"{subdir}/{prefix_key}"})


def validate_graph(g):
    """本地检查：每个节点有 class_type；每条连线指向存在的节点；没有环。ComfyUI 的类型校验只能提交后才知道。"""
    errs = []
    for nid, n in g.items():
        if "class_type" not in n:
            errs.append(f"节点 {nid} 没有 class_type")
        for k, v in (n.get("inputs") or {}).items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int) and v[0] not in g:
                errs.append(f"节点 {nid}.{k} 连到不存在的节点 {v[0]}")
    state = {}
    for start in g:
        stack = [(start, iter([v[0] for v in (g[start].get("inputs") or {}).values() if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in g]))]
        state[start] = 1
        while stack:
            nid, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[nid] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                errs.append(f"连线成环：{nid} -> {nxt}")
            elif state.get(nxt) is None:
                state[nxt] = 1
                stack.append((nxt, iter([v[0] for v in (g[nxt].get("inputs") or {}).values() if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in g])))
    return errs


def load_base(cfg, override=None):
    p = override or get(cfg, "workflow.api_json")
    if not p:
        sys.exit("没有工作流：在 config.yaml 的 workflow.api_json 填你用“导出 (API)”得到的 json 路径（或用 --api-json）。")
    p = Path(p).expanduser()
    if not p.is_file():
        sys.exit(f"工作流文件不存在：{p}")
    g = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(g, dict) or "nodes" in g:
        sys.exit("这看起来是界面格式的 json（有 nodes 列表）。请在 ComfyUI 里用菜单“导出 (API)”（Export (API)）重新导出。")
    return g


# ---------------------------------------------------------------- check-map
def cmd_check_map(a, cfg):
    base = load_base(cfg, a.api_json)
    M = Mapping(cfg)
    ok, warn, err = [], [], []
    virt = sorted({n.get("class_type") for n in base.values() if n.get("class_type") in ("SetNode", "GetNode", "Reroute", "PrimitiveNode")})
    if virt:  # 界面里的"虚拟节点"，正常导出 (API) 时会被展开成真实连线；还留在 json 里说明连线没接实，脚本没法顺着它们改
        warn.append(f"json 里还有虚拟节点 {virt}：它们应该在导出 (API) 时被展开。换新版 ComfyUI 前端重新导出，或手工把这些线接成直连")
    for role, spec in ROLES.items():
        if not M.has(role):
            continue
        nid = M.node(role)
        if nid not in base:
            err.append(f"{role}: 节点 {nid} 不在 json 里")
            continue
        n = base[nid]
        if spec.get("classes") and n["class_type"] not in spec["classes"]:
            warn.append(f"{role}: 节点 {nid} 是 {n['class_type']}，通常是 {'/'.join(spec['classes'])}（你的工作流用了别的节点也可以，但脚本按这个角色去改它的 {M.inp(role) if 'input' in spec or 'prefix' in spec else '连线'}）")
        if "input" in spec:
            name = M.inp(role)
            if name not in n["inputs"]:
                err.append(f"{role}: 节点 {nid}（{n['class_type']}）没有输入 {name!r}；现有输入：{sorted(n['inputs'])}")
                continue
        ok.append(f"{role} -> {nid} {n['class_type']}" + (f".{M.inp(role)}" if "input" in spec or "prefix" in spec else ""))
    for k in M.drop:
        if k not in base:
            err.append(f"drop_nodes: 节点 {k} 不在 json 里")
        else:
            users = [f"{nid}.{i}" for nid, n in base.items() if nid not in M.drop for i, v in n["inputs"].items() if isinstance(v, list) and v and str(v[0]) == k]
            if users:
                err.append(f"drop_nodes: 节点 {k} 被 {users[:4]} 引用，删掉会断线（先在 model_in 等处改接，或别删）")

    def link(nid, inp):
        v = (base.get(nid) or {}).get("inputs", {}).get(inp)
        return (str(v[0]), v[1]) if isinstance(v, list) and len(v) == 2 else None

    def expect(desc, got, want):
        (ok if got == want else warn).append(("连线 OK：" if got == want else "连线和脚本假设不同：") + f"{desc}（实际 {got}，期望 {want}）")

    if M.has("guider") and M.has("cond") and M.node("guider") in base:
        expect("guider.conditioning <- cond 输出0", link(M.node("guider"), "conditioning"), (M.node("cond"), 0))
    if M.has("pass1") and M.node("pass1") in base:
        p1 = M.node("pass1")
        if M.has("guider"):
            expect("pass1.guider <- guider", link(p1, "guider"), (M.node("guider"), 0))
        if M.has("seed"):
            expect("pass1.noise <- seed 节点", link(p1, "noise"), (M.node("seed"), 0))
        if M.has("cond"):
            expect("pass1.latent_image <- cond 输出1", link(p1, "latent_image"), (M.node("cond"), 1))
        for role in ("decode_video", "decode_audio"):
            if M.has(role) and M.node(role) in base:
                expect(f"{role}.samples <- pass1 输出1（二采要把它改接到二采输出）", link(M.node(role), M.inp(role)), (p1, 1))
    if M.has("model_in") and M.has("unet") and M.has("guider") and M.node("guider") in base:
        chain, cur, seen = [], link(M.node("guider"), "model"), set()
        while cur and cur[0] in base and cur[0] not in seen:  # 从引导节点沿 model 输入往上走，应当经过 model_in 节点，最后到 unet 节点
            seen.add(cur[0]); chain.append(cur[0])
            cur = link(cur[0], "model")
        want = [M.node("model_in"), M.node("unet")]
        (ok if all(w in chain for w in want) else warn).append(f"模型链：guider <- {' <- '.join(chain) or '（无）'}；期望经过 model_in 节点 {want[0]} 并到达 unet 节点 {want[1]}")
        if M.has("model_in") and M.node("model_in") in chain and chain.index(M.node("model_in")) == len(chain) - 1:
            ok.append("model_in 就是 unet 加载器本身：dense 开关无补丁可绕开")
    missing = {f: [r for r in rs if not M.has(r)] for f, rs in NEEDS.items()}
    print(f"工作流：{a.api_json or get(cfg, 'workflow.api_json')}（{len(base)} 个节点）\n")
    for x in ok:
        print("[OK]  ", x)
    for x in warn:
        print("[注意]", x)
    for x in err:
        print("[错误]", x)
    print("\n功能是否可用（缺的角色要在 workflow.nodes 里补上）：")
    for f, rs in missing.items():
        print(f"  {'可用' if not rs else '缺 ' + ', '.join(rs):<28s} {f}")
    sys.exit(1 if err else 0)


# ---------------------------------------------------------------- 队列
class Host:
    def __init__(self, cfg, a, dry=False):
        self.url = get(cfg, "host.comfyui_url", "http://127.0.0.1:8188").rstrip("/")
        qd = a.queue_dir or get(cfg, "host.queue_dir")
        self.R = Path(qd) if qd else None
        self.out_dir = Path(get(cfg, "host.comfyui_output", "")) if get(cfg, "host.comfyui_output") else None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 回环地址不该走代理软件
        self.dry = dry

    def log(self, m):
        if self.R:
            with open(self.R / "queue.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%m-%d %H:%M:%S ") + m + "\n")
        print(m, flush=True)

    def call(self, path, body=None, timeout=120):
        req = urllib.request.Request(self.url + path, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with self.opener.open(req, timeout=timeout) as r:
            return json.load(r)


def key_of(s):
    return f"{s['id']}_t{s.get('take', 1)}"


def ready(s, res):
    """first/last/ctx 引用了别的 shot（@id_tN）时，被引用的那条必须 success。"""
    return all(res.get(v[1:].split(":")[0], {}).get("status") == "success" for v in (s.get("first"), s.get("last"), s.get("ctx")) if v and v.startswith("@"))


def sheet(ff, video, fr, out, fps=24):
    """八帧联系表（4×2，每格标时间）：每段出完先扫一眼。"""
    from PIL import Image, ImageDraw
    dur = fr / fps
    im = Image.new("RGB", (400 * 4, 247 * 2), "#17252c")
    d = ImageDraw.Draw(im)
    for j in range(8):
        t = dur * (j + 0.5) / 8
        buf = subprocess.check_output([ff, "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=400:226", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
        x, y = j % 4 * 400, j // 4 * 247
        im.paste(Image.frombytes("RGB", (400, 226), buf), (x, y))
        d.text((x + 6, y + 229), f"{t:.1f}s", fill="white")
    im.save(out, quality=82)


def cmd_run(a, cfg):
    H = Host(cfg, a, a.dry_run)
    M = Mapping(cfg)
    base = load_base(cfg, a.api_json)
    if a.dry_run:
        return dry_run(a, cfg, H, M, base)
    if not H.R:
        sys.exit("没有队列目录：config.yaml 的 host.queue_dir 或 --queue-dir")
    if not H.out_dir:
        sys.exit("需要 config.yaml 的 host.comfyui_output（ComfyUI 的 output 目录），用来找到渲好的片子")
    R = H.R
    assets = Assets(cfg, R, False)
    fps = float(get(cfg, "project.fps", 24))
    H.log("queue start")
    while not (R / "STOP").exists():
        try:
            shots = json.loads((R / "shots.json").read_text(encoding="utf-8"))  # 每轮重读：队列运行中可以随时改
            rp = R / "results.json"
            res = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
            todo = [s for s in shots if res.get(key_of(s), {}).get("status") != "success" and res.get(key_of(s), {}).get("tries", 0) < 2]  # 同一条最多试 2 次
            todo = [s for s in todo if ready(s, res)]
            if not todo:
                time.sleep(60)
                continue
            s = todo[0]
            key = key_of(s)
            tries = res.get(key, {}).get("tries", 0) + 1
            t0 = time.monotonic()
            try:
                g, fr, _ = build_graph(base, M, s, cfg, assets)
                errs = validate_graph(g)
                if errs:
                    raise MapError("; ".join(errs[:5]))
            except MapError as e:
                _record(rp, key, {"status": "error", "tries": tries, "messages": ["映射/连线错误：" + str(e)[:800]], "finished": time.strftime("%H:%M")})
                H.log(f"END {key} error (graph) {e}")
                continue
            H.log(f"BEGIN {key} {s['seconds']}s")
            try:
                pid = H.call("/prompt", {"prompt": g, "client_id": "h3-drama-queue"})["prompt_id"]
            except urllib.error.HTTPError as e:  # ComfyUI 校验没通过：记下原因并计一次失败，不要无限重试同一张废图
                body = e.read().decode(errors="replace")[:1500]
                _record(rp, key, {"status": "error", "tries": tries, "messages": ["ComfyUI 拒绝了工作流：" + body], "finished": time.strftime("%H:%M")})
                H.log(f"END {key} error (rejected) {body[:200]}")
                continue
            while True:
                h = H.call("/history/" + pid).get(pid)
                if h:
                    break
                time.sleep(8)
            r = {"status": h["status"]["status_str"], "seconds_wall": round(time.monotonic() - t0), "frames": fr, "tries": tries, "finished": time.strftime("%H:%M")}
            if r["status"] == "success":
                vids = [v for o in h["outputs"].values() for vs in o.values() if isinstance(vs, list) for v in vs
                        if isinstance(v, dict) and str(v.get("filename", "")).endswith(".mp4") and str(v.get("filename", "")).startswith(key + "_")]  # 跳过 LoadVideo 的预览（ctx 片段）
                if not vids:  # 采样成功但历史里找不到以 <key>_ 开头的 mp4：多半是 save 节点的 filename_prefix 没改成功
                    r["status"], r["messages"] = "error", ["history 的输出里没有 " + key + "_ 开头的 mp4"]
                else:
                    v = sorted(vids, key=lambda v: "_stage1" in v["filename"])[0]  # 要最终成片，不是一采预览
                    video = H.out_dir / v["subfolder"] / v["filename"]
                    r["video"] = str(video)
                    try:
                        sheet(assets.ff, video, fr, R / f"{key}.sheet.jpg", fps)
                    except Exception as e:
                        r["sheet_error"] = str(e)[:200]  # 多半是主机上 ffmpeg 不可用；成片本身没问题
            else:
                r["messages"] = [str(m)[:800] for m in h["status"].get("messages", [])[-2:]]
            _record(rp, key, r)
            H.log(f"END {key} {r['status']} {r['seconds_wall']}s")
            try:
                H.call("/free", {"unload_models": True, "free_memory": True})  # 每段从干净的显存开始；ComfyUI 不会自己释放
                time.sleep(10)
            except Exception as e:
                H.log("free failed " + str(e)[:120])
        except Exception:
            H.log("ERROR " + traceback.format_exc()[-600:])
            time.sleep(60)
    H.log("queue stop")


def _record(rp, key, r):
    res = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    res[key] = r
    rp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def dry_run(a, cfg, H, M, base):
    shots_path = Path(a.shots) if a.shots else (H.R / "shots.json" if H.R else None)
    if not shots_path or not shots_path.is_file():
        sys.exit("dry-run 需要 --shots shots.json（或配置 host.queue_dir）")
    shots = json.loads(shots_path.read_text(encoding="utf-8"))
    only = set(a.only.split(",")) if a.only else None
    sel = [s for s in shots if (not only or key_of(s) in only or s["id"] in only)]
    if not sel:
        sys.exit("没有选中任何 shot（--only 可写 id 或 id_tN）")
    if not a.all and not only:
        sel = sel[:1]
    assets = Assets(cfg, H.R, True)
    if a.save_dir:
        Path(a.save_dir).mkdir(parents=True, exist_ok=True)
    bad = 0
    for s in sel:
        key = key_of(s)
        print(f"\n===== [dry-run] {key}  {s.get('kind', '')}  {s['seconds']} s  seed {s['seed']}  参考图 {len(s['images'])} 张 =====")
        if not s.get("up2") and not s.get("sigmas"):
            print("  [注意] 这条 shot 没写 up2/sigmas：" + OLD_DEFAULT_NOTE + "（建议用 build_shots.py 生成完整配方字段）")
        try:
            g, fr, notes = build_graph(base, M, s, cfg, assets)
        except MapError as e:
            print("  [映射错误]", e)
            bad += 1
            continue
        errs = validate_graph(g)
        added = sorted(k for k in g if k not in base)
        changed = sorted(k for k in g if k in base and g[k] != base[k])
        print(f"  帧数 {fr}（{fr / float(get(cfg, 'project.fps', 24)):.2f} 秒）；节点 {len(base)} -> {len(g)}；改动：")
        for n in notes:
            print("   -", n)
        names = lambda ks: ", ".join("%s(%s)" % (k, g[k]["class_type"]) for k in ks)
        print(f"   - 新增节点 {len(added)} 个：{names(added)}")
        print(f"   - 被改写的原节点 {len(changed)} 个：{names(changed)}")
        print("  连线完整性：" + ("通过（每条连线都指向存在的节点，无环）" if not errs else "失败 " + "; ".join(errs[:6])))
        bad += bool(errs)
        if a.save_dir:
            (Path(a.save_dir) / f"{key}.api.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  已写 {Path(a.save_dir) / (key + '.api.json')}")
        if a.print_json or (len(sel) == 1 and not a.save_dir):
            print(json.dumps(g, ensure_ascii=False, indent=1))
    print("\n[dry-run] 没有联网，没有写 results.json。")
    sys.exit(1 if bad else 0)


# ---------------------------------------------------------------- submit
def cmd_submit(a, cfg):
    rnd = json.loads(Path(a.round).read_text(encoding="utf-8"))
    master_p = Path(a.master)
    master = json.loads(master_p.read_text(encoding="utf-8")) if master_p.exists() else []
    keys = {key_of(s) for s in rnd}
    kept = [m for m in master if key_of(m) not in keys]  # 同 id 同 take 的旧条目被新的替换；其余原样保留
    merged = kept + rnd
    print(f"总清单 {len(master)} 条 + 本轮 {len(rnd)} 条（替换同键 {len(master) - len(kept)} 条）= {len(merged)} 条；本轮：{', '.join(sorted(keys))}")
    ssh, qd = get(cfg, "host.ssh"), get(cfg, "host.queue_dir")
    remote = str(qd).replace("\\", "/").rstrip("/") if qd else ""  # Windows 主机的路径写成 D:/dir 形式，scp 才认
    cmd = ["scp", "-q", str(master_p), f"{ssh}:{remote}/shots.json"] if ssh and qd else None
    if a.dry_run:
        print("[dry-run] 不写文件。" + (f"--upload 时将执行：{' '.join(cmd)}" if cmd else "（host.ssh 或 host.queue_dir 没填：--upload 不可用）"))
        return
    master_p.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写 {master_p}")
    if a.upload:
        if not cmd:
            sys.exit("--upload 需要 config.yaml 的 host.ssh 和 host.queue_dir；也可以自己把 shots.json 拷到主机的队列目录")
        subprocess.check_call(cmd)
        print("已上传到主机的队列目录（队列每轮重读 shots.json，无需重启）")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="跑队列；--dry-run 只生成并打印工作流 json")
    r.add_argument("--dry-run", action="store_true", help="不联网：按映射表改写你的工作流，打印改动和（单条时）完整 json")
    r.add_argument("--shots", help="dry-run 用的 shots.json（默认读 host.queue_dir/shots.json）")
    r.add_argument("--only", help="dry-run 只看这几条：id 或 id_tN，逗号分隔")
    r.add_argument("--all", action="store_true", help="dry-run 处理所有 shot（默认只处理第一条）")
    r.add_argument("--save-dir", help="dry-run 把每条的工作流 json 写到这个目录")
    r.add_argument("--print-json", action="store_true", help="dry-run 多条时也打印完整 json")
    r.add_argument("--queue-dir", help="队列目录（默认读 host.queue_dir）")
    r.add_argument("--api-json", help="导出的工作流 json（默认读 workflow.api_json）")
    c = sub.add_parser("check-map", help="对照导出的 json 检查 workflow 映射表")
    c.add_argument("--api-json", help="导出的工作流 json（默认读 workflow.api_json）")
    s = sub.add_parser("submit", help="把一轮 shots 合并进总 shots.json")
    s.add_argument("round", help="build_shots.py 出的这一轮 json")
    s.add_argument("--master", default="shots.json", help="总 shots.json（默认当前目录）")
    s.add_argument("--upload", action="store_true", help="合并后用 scp 传到 host.ssh:host.queue_dir/shots.json")
    s.add_argument("--dry-run", action="store_true", help="只打印合并结果和 scp 命令，不写文件")
    for p in (r, c, s):
        add_config_arg(p)
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):  # Windows 主机的控制台默认不是 UTF-8，中文输出会报错
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    cfg = load_config(a.config)
    try:
        {"run": cmd_run, "check-map": cmd_check_map, "submit": cmd_submit}[a.cmd](a, cfg)
    except MapError as e:
        sys.exit(f"映射错误：{e}")


if __name__ == "__main__":
    main()

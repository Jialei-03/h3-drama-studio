#!/usr/bin/env python3
"""把一份"分段提示词"数据文件（yaml）组装成出片队列用的 shots.json，同时生成逐句中文翻译 prompts_zh.md。

输入：数据文件，写法见 examples/gemini-revenge/data/segments.example.yaml，字段骨架见
      skills/drama-scenes/references/prompt-structure.md。数据里每个文字字段都写 {en, zh} 两份，
      英文拿去渲染、中文给人审，由同一份数据生成所以一一对应。
输出：shots.json（每段一条：id、take、seed、seconds、images、prompt、配方字段、首尾帧/接续锚点）
      和 prompts_zh.md（每段完整提示词的中文版）。
预设：
  文戏 kind: dialogue —— 专属二采，不挂 LoRA；
  武戏 kind: fight    —— 同样的二采，再挂 config.yaml 的 models.fight_loras；段里写了 ctx 就接上一段末尾 22 帧。
  采样参数默认值见 skills/h3-video/references/recipes.md，可在 config.yaml 的 recipe: 里改。

用法示例：
  python3 scripts/build_shots.py segments.yaml --out shots.json
  python3 scripts/build_shots.py segments.yaml --take 530 --only f2,f3 --out round_530.json   # 只出这两段，take 号 530
  python3 scripts/build_shots.py segments.yaml --dry-run                                         # 只打印，不写文件

状态：本机用示例数据验证了组装和占位符解析；未在干净环境端到端验证（shots.json 没有真的送进 ComfyUI）。
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import add_config_arg, get, load_config  # noqa: E402

RH10 = "1, .9882, .973, .9524, .9231, .878, .8, .6316, .4737, .1579, 0"  # 一采 10 步 sigma 曲线，出处见 skills/h3-video/references/credits.md

# 脚本自带的默认句子，数据文件里的 anchor_text / kinds / retained 可以覆盖
DEFAULT_ANCHOR = {
    "first": {"en": "The video opens exactly on the anchored first frame and continues it without a cut: ",
              "zh": "视频严格从锚定的首帧开始，无剪切地接着往下演："},
    "last": {"en": " The video ends exactly on the anchored last frame.", "zh": "视频严格停在锚定的尾帧上。"},
    "ctx": {"en": "The video opens in the middle of the previous shot and continues it seamlessly: ",
            "zh": "视频从上一段的中途直接开始，无缝接着往下演："},
    "positions": {"en": "Continuing from the previous frame. ", "zh": "接续上一画面。"},
}
DEFAULT_KINDS = {
    "fight": {"structure_extra": {"en": "The video consists of exactly the shots written below, in that order.",
                                  "zh": "视频只由下面这几个镜头按顺序组成。"}},
}
RETAINED = {
    "person": {"en": "the face, hairstyle, outfit, accessories, and signature color are retained.", "zh": "面部、发型、服装、配饰和标志色全部保留。"},
    "creature": {"en": "the shape, colors, materials and details are retained.", "zh": "形态、颜色、材质和细节全部保留。"},
    "scene": {"en": "the layout, architecture, lighting, and key landmarks are retained.", "zh": "布局、建筑、光线和关键地标全部保留。"},
}
LABEL = {"en": "<Subject {}>", "zh": "<主体{}>"}
PIC = {"en": "<Picture {}>", "zh": "<图{}>"}
SHOT = {"en": "[Shot {}]", "zh": "[镜头{}]"}
WORDS = {"en": {"is": " is ", "end": ".", "appears": "appears in", "pos": "Positions: ", "nocut": " No whoosh or transition sound is added at the hard cuts."},
         "zh": {"is": "是", "end": "。", "appears": "出现在", "pos": "人物站位：", "nocut": "硬切处不加呼啸声或转场音。"}}


class DataError(Exception):
    pass


TC_HEAD = re.compile(r"^\s*\d+(?:\.\d+)?\s*[–—-]\s*\d+(?:\.\d+)?\s*(?:s|sec|秒)\.?\s*")


def after_timecode(pre, text):
    """锚点句放在时间码后面：武戏每个镜头必须以时间码开头（check_script 会查）。"""
    m = TC_HEAD.match(text)
    return text[:m.end()] + pre + text[m.end():] if m else pre + text


def tx(v, lang, where=""):
    """取一个 {en, zh} 字段的某种语言；写成纯字符串则两种语言共用；缺 zh 时退回英文并记一条警告。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if lang in v and v[lang] is not None:
        return str(v[lang])
    WARN.append(f"{where or '某字段'} 缺 {lang} 版本，用 en 代替")
    return str(v.get("en", ""))


WARN = []


def load_data(path):
    try:
        import yaml
    except ImportError:
        sys.exit("缺少 PyYAML：pip install pyyaml")
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for k in ("characters", "segments"):
        if not d.get(k):
            raise DataError(f"数据文件缺少 {k}")
    ids = [s["id"] for s in d["segments"]]
    if len(set(ids)) != len(ids):
        raise DataError("segments 里有重复的 id：" + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    d.setdefault("phrases", {}); d.setdefault("voices", {}); d.setdefault("kinds", {})
    return d


class Resolver:
    """把一段文字里的 {@短语}、{V_说话人}、{角色} 换成真正的内容。"""

    def __init__(self, data, seg, lang, readable=False):
        self.d, self.seg, self.lang, self.readable = data, seg, lang, readable
        self.refs = list(seg.get("refs") or [])
        self.label = {}
        if readable:  # 给人看的全剧本：{GEM} 直接换成名字，不用 <Subject N>
            return
        for i, r in enumerate(self.refs, 1):
            self.label[r] = LABEL[lang].format(i)
        for r in self.refs:  # 受损阶段的场景图等"替身"：{ARENA} 可以指到它
            alias = data["characters"][r].get("stand_in_for")
            if alias and alias not in self.label:
                self.label[alias] = self.label[r]

    def name(self, key):
        c = self.d["characters"].get(key)
        return tx(c.get("name", key), self.lang, f"characters.{key}.name") if c else None

    def __call__(self, text, where=""):
        text = tx(text, self.lang, where) if not isinstance(text, str) else text
        for _ in range(6):  # 短语里可以再引用短语
            new = re.sub(r"\{@(\w+)\}", lambda m: self._phrase(m.group(1), where), text)
            if new == text:
                break
            text = new
        text = re.sub(r"\{V_(\w+)\}", lambda m: self._voice(m.group(1), where), text)
        text = re.sub(r"\{(\w+)\}", lambda m: self._subject(m.group(1), where), text)
        if self.lang == "zh":  # yaml 折行会在汉字之间留下空格，中文里去掉
            text = re.sub(r"(?<=[一-鿿，。；：！？、）」])[ \t]+(?=[一-鿿（「])", "", text)
        return text

    def _phrase(self, k, where):
        if k not in self.d["phrases"]:
            raise DataError(f"{where}: 找不到短语 {{@{k}}}（phrases 里没有）")
        return tx(self.d["phrases"][k], self.lang, f"phrases.{k}")

    def _voice(self, k, where):
        if k not in self.d["voices"]:
            raise DataError(f"{where}: 找不到声线 {{V_{k}}}（voices 里没有）")
        if self.readable and self.lang == "zh" and self.name(k):  # 给人看的剧本：写"某某的声音"，不展开整段声线描述
            return f"{self.name(k)}的声音"
        return tx(self.d["voices"][k], self.lang, f"voices.{k}")

    def _subject(self, k, where):
        if k in self.label:
            return self.label[k]
        n = self.name(k)
        if n is None:
            raise DataError(f"{where}: 找不到 {{{k}}}（characters 里没有，也不是 {{@短语}} 或 {{V_声线}}）")
        return n


def segment_pieces(d, seg, lang, readable=False):
    """一段的各个部分（已解析占位符）：返回 dict。render() 和 make_full_script 共用。
    readable=True 用于给人看的剧本：角色用名字，不插入给模型看的锚点句。"""
    R = Resolver(d, seg, lang, readable)
    sid = seg["id"]
    W = WORDS[lang]
    kind = seg.get("kind", "dialogue")
    anchors = {**DEFAULT_ANCHOR, **(d.get("anchor_text") or {})}
    shots = [R(s, f"{sid}.shots[{i}]") for i, s in enumerate(seg["shots"], 1)]
    if not shots:
        raise DataError(f"{sid}: 没有镜头")
    if readable:
        pass
    elif seg.get("first") and not seg.get("ctx"):
        pre = tx(anchors["first"], lang)
        if pre.strip()[:30] not in shots[0]:
            shots[0] = after_timecode(pre, shots[0])
    if seg.get("ctx") and not readable:
        pre = tx(anchors["ctx"], lang)
        if pre.strip()[:30] not in shots[0]:
            shots[0] = after_timecode(pre, shots[0])
    if seg.get("last") and not readable:
        post = tx(anchors["last"], lang)
        if post.strip() not in shots[-1]:
            shots[-1] = shots[-1].rstrip() + post
    n = len(shots)
    numbered = [f"{SHOT[lang].format(i)} {s.strip()}" for i, s in enumerate(shots, 1)]
    if n == 1:
        structure = tx({"en": "The whole video is one continuous shot with no cuts.", "zh": "整段视频是一个不剪切的连续镜头。"}, lang)
    else:
        structure = (f"The video is {n} shots joined by hard cuts: every cut is a straight cut, with no dissolve, no fade and no transition effect."
                     if lang == "en" else f"视频由 {n} 个镜头硬切衔接：每一刀都是直接切，没有叠化、没有淡入淡出、没有转场特效。")
    kcfg = {**DEFAULT_KINDS.get(kind, {}), **(d["kinds"].get(kind) or {})}  # 预设：数据文件里的 kinds 覆盖脚本自带的
    extra = tx(kcfg["structure_extra"], lang, f"kinds.{kind}.structure_extra") if kcfg.get("structure_extra") else ""
    power = ("; " if lang == "en" else "；").join(tx(d["characters"][r]["power"], lang, f"characters.{r}.power")
                                              for r in R.refs if d["characters"][r].get("power"))
    ctx_parts = []
    if kcfg.get("context"):
        ctx_parts.append(R(kcfg["context"], f"kinds.{kind}.context"))
    if seg.get("context"):
        ctx_parts.append(R(seg["context"], f"{sid}.context"))
    pos = R(seg["positions"], f"{sid}.positions") if seg.get("positions") else ""
    if pos and not pos.startswith(W["pos"]):
        pos = W["pos"] + pos
    if pos and (seg.get("first") or seg.get("ctx")) and not readable:
        pos = pos.replace(W["pos"], W["pos"] + tx(anchors["positions"], lang), 1) if tx(anchors["positions"], lang) not in pos else pos
    defs, ret = [], []
    for j, r in enumerate(R.refs, 1):
        c = d["characters"][r]
        dfn = R(tx(c["define"], lang, f"characters.{r}.define").replace("{p}", PIC[lang].format(j)), f"characters.{r}.define")
        if readable:
            break
        defs.append(R.label[r] + W["is"] + dfn.strip().rstrip(".。") + W["end"])
        where = [SHOT[lang].format(k) for k, s in enumerate(shots, 1)
                 if c.get("kind", "person") == "scene" or R.label[r] in s or (R.name(r) and R.name(r) in s)]
        keep = tx(c["retained"], lang) if c.get("retained") else tx(RETAINED[c.get("kind", "person")], lang)
        ret.append(f"{R.label[r]} ({W['appears']} {', '.join(where) or SHOT[lang].format(1)}): fully_preserved - {keep}")
    sound = R(seg.get("soundscape", ""), f"{sid}.soundscape")
    if n > 1:
        sound = sound.rstrip() + W["nocut"]
    return dict(defs=defs, summary=R(seg["summary"], f"{sid}.summary"), ret=ret, style=R(d.get("style", ""), "style"), power=power,
                context=ctx_parts, structure=structure, extra=extra, positions=pos, shots=numbered, sound=sound, n=n, kind=kind)


def render(d, seg, lang):
    p = segment_pieces(d, seg, lang)
    sep = ". " if lang == "en" else "。"
    head = (" " if lang == "en" else "").join(x for x in [p["style"].strip(), (p["power"] + sep.strip()) if p["power"] else "", *[c.strip() for c in p["context"]], p["structure"], p["extra"]] if x)
    body = head + "\n" + (p["positions"] + "\n" if p["positions"] else "") + "\n".join(p["shots"])
    return ("subject_definitions:\n" + "\n".join(p["defs"]) + "\n\nsummary:\n[reference generation] " + p["summary"] +
            "\n\nretention_analysis:\n" + "\n".join(p["ret"]) + "\n\ndetailed_description:\n" + body +
            "\n\noverall_soundscape:\n" + p["sound"] + "\n\nnon_diegetic_music:\nN/A")


def frames_for(seconds, ctx_frames=0):
    """与 drama_queue.py 一致：秒数换算成帧数，加上接续帧，向上取到 17k+5。"""
    fr = max(5, round(seconds * 24) + ctx_frames)
    return fr + (5 - fr % 17) % 17


def recipe_for(kind, cfg):
    """文戏/武戏的采样预设。只写 config 里有值的字段，没写的字段交给用户自己的工作流。"""
    r = {}
    if get(cfg, "models.unet"):
        r["unet"] = get(cfg, "models.unet")
    if get(cfg, "models.text_encoder"):
        r["clip"] = get(cfg, "models.text_encoder")
    r.update(w=get(cfg, "recipe.stage1.w", 1024), h=get(cfg, "recipe.stage1.h", 576),
             sigmas=get(cfg, "recipe.stage1.sigmas", RH10), sampler=get(cfg, "recipe.stage1.sampler", "euler"),
             shift=get(cfg, "recipe.shift", [12, 3]),
             up2={"w": get(cfg, "recipe.up2.w", get(cfg, "project.width", 1536)), "h": get(cfg, "recipe.up2.h", get(cfg, "project.height", 864)),
                  "sched": get(cfg, "recipe.up2.sched", ["beta", 14]), "split": get(cfg, "recipe.up2.split", 8),
                  "sampler": get(cfg, "recipe.up2.sampler", "euler")})
    if get(cfg, "recipe.save_stage1", False):
        r["save_stage1"] = True
    if kind == "fight":
        loras = get(cfg, "models.fight_loras", []) or []
        if not loras:
            WARN.append("config.yaml 的 models.fight_loras 为空：武戏段不会挂任何 LoRA")
        r["loras"] = [[l["name"], l["strength"]] for l in loras]
    return r


def resolve_anchor(v, takes):
    """'@id' 换成 '@id_t<该段本轮的 take>'；已经写成 '@id_t3' 或 '@id_t3:end' 的原样保留；普通文件名原样保留。"""
    if not isinstance(v, str) or not v.startswith("@"):
        return v
    key, _, pick = v[1:].partition(":")
    if re.search(r"_t\d+$", key):
        return v
    if key not in takes:
        raise DataError(f"锚点 {v} 指向的段 {key} 不在数据文件里")
    return "@" + key + "_t" + str(takes[key]) + (":" + pick if pick else "")


def build(d, cfg, take=None, only=None, kind_only=None, with_recipe=True):
    segs = d["segments"]
    default_take = int(get(d, "defaults.take", 1))
    selected = [s for s in segs if (not only or s["id"] in only) and (not kind_only or s.get("kind", "dialogue") == kind_only)]
    if only and (miss := set(only) - {s["id"] for s in segs}):
        raise DataError(f"--only 里有数据文件没有的段：{sorted(miss)}")
    sel_ids = {s["id"] for s in selected}
    takes = {s["id"]: int(take if (take is not None and s["id"] in sel_ids) else s.get("take", default_take)) for s in segs}
    out = []
    for s in selected:
        for r in s.get("refs") or []:
            if r not in d["characters"]:
                raise DataError(f"{s['id']}: refs 里的 {r} 不在 characters 里")
        if len(s.get("refs") or []) > 9:
            raise DataError(f"{s['id']}: 参考图 {len(s['refs'])} 张，超过 H3 的 9 张上限")
        kind = s.get("kind", "dialogue")
        if kind not in ("dialogue", "fight"):
            raise DataError(f"{s['id']}: kind 只能是 dialogue 或 fight，现在是 {kind!r}")
        seed = s.get("seed", get(d, "defaults.seed", 7100))
        e = {"id": s["id"], "take": takes[s["id"]], "kind": kind, "seconds": s["seconds"], "seed": seed,
             "images": [d["characters"][r]["image"] for r in s.get("refs") or []], "refs": list(s.get("refs") or []),
             "prompt": render(d, s, "en")}
        if with_recipe:
            e.update(recipe_for(kind, cfg))
        for slot in ("first", "last", "ctx"):
            if s.get(slot):
                e[slot] = resolve_anchor(s[slot], takes)
        if kind != "fight" and s.get("ctx"):
            WARN.append(f"{s['id']}: 文戏段写了 ctx（接续）——文戏一般站位对上就硬切，不接续")
        if s.get("recipe"):  # 单段覆盖
            e.update(copy.deepcopy(s["recipe"]))
        out.append(e)
    return out


def zh_markdown(d, cfg, segs_sel, shots):
    chars = d["characters"]
    title = tx(d.get("title", "提示词"), "zh")
    md = [f"# {title}：全部提示词（中文翻译）\n\n",
          "下面是每一段送进 H3 的完整提示词的逐句中文翻译。实际生成用英文原文（台词保留中文），原文在 shots.json，"
          "两者由同一份数据生成，内容一一对应。\n\n格式是 MiniMax 官方 H3 提示词的 Ref2VA 六段式：主体定义、概要、保留分析、详细描述、整体声音、配乐（留空）。\n"]
    for s, e in zip(segs_sel, shots):
        anchors = [f"{lab}：{e[k]}" for k, lab in (("first", "首帧"), ("last", "尾帧"), ("ctx", "接续")) if e.get(k)]
        names = "、".join(tx(chars[r].get("name", r), "zh") for r in s.get("refs") or [])
        md.append(f"\n## {s['id']}　{s['seconds']} 秒　（{'武戏' if e['kind'] == 'fight' else '文戏'}）\n\n参考图：{names}"
                  + ("　｜　" + "；".join(anchors) if anchors else "") + f"\n\n```text\n{render(d, s, 'zh')}\n```\n")
    return "".join(md)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", help="分段提示词数据文件（yaml）")
    ap.add_argument("--out", help="shots.json 的输出路径（默认：数据文件旁边的 shots.json）")
    ap.add_argument("--zh-out", help="中文翻译 md 的输出路径（默认：与 --out 同目录的 prompts_zh.md）")
    ap.add_argument("--take", type=int, help="本轮 take 号（覆盖被选中各段的 take）；改了提示词就换号，否则队列认为出过了")
    ap.add_argument("--only", help="只组装这几段，逗号分隔的 id")
    ap.add_argument("--kind", choices=["dialogue", "fight"], help="只组装文戏或只组装武戏")
    ap.add_argument("--no-recipe", action="store_true", help="不写采样配方字段（不推荐：队列会落到旧的单采默认值）")
    ap.add_argument("--dry-run", action="store_true", help="只在屏幕上打印将要写入的 shots.json 和统计，不写任何文件")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    try:
        d = load_data(a.data)
        shots = build(d, cfg, a.take, set(a.only.split(",")) if a.only else None, a.kind, not a.no_recipe)
        sel = [s for s in d["segments"] if s["id"] in {e["id"] for e in shots}]
        zh = zh_markdown(d, cfg, sel, shots)
    except DataError as e:
        sys.exit(f"数据错误：{e}")
    print(f"{len(shots)} 段，合计 {sum(e['seconds'] for e in shots)} 秒；文戏 {sum(e['kind'] == 'dialogue' for e in shots)}，武戏 {sum(e['kind'] == 'fight' for e in shots)}", file=sys.stderr)
    for e in shots:
        left = re.findall(r"\{[^{}]*\}", e["prompt"])
        n_shot = len(re.findall(r"^\[Shot \d+\]", e["prompt"], re.M))
        extra = ""
        if e.get("loras"):
            extra += "  loras %d" % len(e["loras"])
        for k in ("ctx", "first", "last"):
            if e.get(k):
                extra += f"  {k} {e[k]}"
        if left:
            extra += "  【残留占位符 %s】" % left
        print(f"  {e['id']}_t{e['take']:<4} {e['kind']:9s} {e['seconds']:>5} s  镜头 {n_shot}  英文 {len(e['prompt'].split())} 词  图 {len(e['images'])}{extra}", file=sys.stderr)
    for w in sorted(set(WARN)):
        print("  [警告]", w, file=sys.stderr)
    if a.dry_run:
        print(json.dumps(shots, ensure_ascii=False, indent=1))
        print("[dry-run] 没有写任何文件", file=sys.stderr)
        return
    out = Path(a.out) if a.out else Path(a.data).resolve().parent / "shots.json"
    zh_out = Path(a.zh_out) if a.zh_out else out.parent / "prompts_zh.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
    zh_out.write_text(zh, encoding="utf-8")
    print(f"写入 {out} 和 {zh_out}", file=sys.stderr)


if __name__ == "__main__":
    main()

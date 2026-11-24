#!/usr/bin/env python3
"""从同一份分段数据生成给人看的中文全剧本：全集结构表、全片状态表、每段的画面/台词/声音和"怎么生成的"。

输入：build_shots.py 的数据文件（segments.yaml）；可选 --status（每段用哪一版、进度）；可选 --shots（带上 shots.json 里的种子和 take）。
输出：一份 markdown。审稿时把它和 prompts_zh.md（逐句翻译）一起交给用户过目，用户确认才排队出片（见 drama-preproduction/references/review.md）。
和 prompts_zh.md 的区别：这里角色直接写名字，不出现 <主体N>，也不含给模型看的锚点句，是读故事用的。

用法示例：
  python3 scripts/make_full_script.py segments.yaml --out full_script.md
  python3 scripts/make_full_script.py segments.yaml --status status.yaml --shots shots.json --out full_script.md
  python3 scripts/make_full_script.py segments.yaml --dry-run     # 只在屏幕上打印

status.yaml 的写法（可省略）：
  g2: {take: t106, note: "已出，留用"}
  f1: {take: "-", note: "待出"}

状态：本机用示例数据验证过输出；未在干净环境端到端验证。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import add_config_arg, get, load_config  # noqa: E402
import build_shots as B  # noqa: E402


def anchor_text(v, slot, status):
    if not v:
        return None
    if not str(v).startswith("@"):
        return f"图片 `{v}`"
    key, _, pick = v[1:].partition(":")
    sid = key.rsplit("_t", 1)[0]
    take = (status.get(sid) or {}).get("take") or "t" + key.rsplit("_t", 1)[-1]
    frame = "最后一帧" if (slot == "first" and pick != "start") or pick == "end" else "第一帧"
    return f"{sid}（{take}）实际生成出来的{frame}"


def clean(text):
    """去掉只对模型有用的标记：说话人编号 (S1)。"""
    return re.sub(r"\s*\(S\d\)\s*", "", text)


def build_doc(d, cfg, status, shots_by_id):
    zh = lambda v, w="": B.tx(v, "zh", w)
    chars = d["characters"]
    title = zh(d.get("title", "分段剧本"))
    segs = d["segments"]
    out = [f"# {title}：完整剧本与生成方法\n\n",
           f"全集 {len(segs)} 段，合计 {sum(s['seconds'] for s in segs)} 秒。英文提示词原文在 shots.json，逐句中文翻译在 prompts_zh.md，"
           "本文件是给人看的剧本版：每段的画面、台词、声音，以及它是怎么生成的。\n"]
    recipe = B.recipe_for("dialogue", cfg)
    fl = get(cfg, "models.fight_loras", []) or []
    lora_txt = "、".join("%s %s" % (l["name"], l["strength"]) for l in fl) or "（models.fight_loras 未填）"
    out.append("\n## 通用生成方法\n\n| 项 | 设置 |\n| --- | --- |\n"
               f"| 底模 | `{get(cfg, 'models.unet', '（config.yaml 的 models.unet 未填）')}` |\n"
               f"| 文本编码器 | `{get(cfg, 'models.text_encoder', '（models.text_encoder 未填）')}` |\n"
               f"| 采样 | 专属二采：一采 {recipe['w']}×{recipe['h']}、{recipe['sampler']}、10 步 → 潜空间放大 → 二采 {recipe['up2']['w']}×{recipe['up2']['h']}"
               f"（{recipe['up2']['sched'][0]} {recipe['up2']['sched'][1]} 步，第 {recipe['up2']['split']} 步切开）；SigmaShift {recipe['shift']} |\n"
               f"| 文戏 | 不挂 LoRA；不写时间码；站位对上就硬切 |\n"
               f"| 武戏 | 挂 LoRA 链：{lora_txt}；每个镜头写时间码；接续段接上一段末尾 22 帧加音频 |\n"
               f"| 帧率与成片 | {get(cfg, 'project.fps', 24)} fps，{get(cfg, 'project.width', 1536)}×{get(cfg, 'project.height', 864)}，带同期声（台词、音效），不加配乐 |\n"
               "| 参考图 | 每段把出场角色、召唤物和场景的定妆图一起送进参考生视频（最多 9 张），见各段 |\n")
    out.append("\n## 全集结构\n\n| # | 段 | 内容 | 类型 | 时长 | 用哪一版 | 状态 |\n| --- | --- | --- | --- | ---: | --- | --- |\n")
    for n, s in enumerate(segs, 1):
        st = status.get(s["id"]) or {}
        sh = shots_by_id.get(s["id"]) or {}
        take = st.get("take") or (f"t{sh['take']}" if sh.get("take") else "—")
        out.append(f"| {n} | {s['id']} | {s.get('title', '')} | {'武戏' if s.get('kind') == 'fight' else '文戏'} | {s['seconds']} 秒 | {take} | {st.get('note', '待出')} |\n")
    labelled = [(k, v) for k, v in d["phrases"].items() if isinstance(v, dict) and v.get("label")]
    if labelled:
        R0 = B.Resolver(d, {"refs": []}, "zh", readable=True)
        out.append("\n## 全片状态表（每段的人物站位都由这些固定说法拼成，状态改变前一字不变）\n\n| 项 | 状态 | 适用段 |\n| --- | --- | --- |\n")
        for k, v in labelled:
            out.append(f"| {v['label']} | {clean(R0(v, f'phrases.{k}'))} | {v.get('applies', '')} |\n")
    for n, s in enumerate(segs, 1):
        sid = s["id"]
        p = B.segment_pieces(d, s, "zh", readable=True)
        st = status.get(sid) or {}
        sh = shots_by_id.get(sid) or {}
        out.append(f"\n---\n\n## {n}. {sid}　{s.get('title', '')}（{s['seconds']} 秒，{'武戏' if p['kind'] == 'fight' else '文戏'}）\n\n**概要**：{p['summary']}\n\n**生成方法**\n\n")
        names = "、".join(f"{zh(chars[r].get('name', r))}（`{chars[r]['image']}`）" for r in s.get("refs") or [])
        out.append(f"- 参考图：{names or '无'}\n")
        anchors = [x for x in (("首帧 = " + anchor_text(s.get("first"), "first", status)) if s.get("first") else None,
                               ("尾帧 = " + anchor_text(s.get("last"), "last", status)) if s.get("last") else None,
                               ("接续 = 上一段 " + anchor_text(s.get("ctx"), "ctx", status) + " 的末尾 22 帧加音频") if s.get("ctx") else None) if x]
        why = f"。原因：{zh(s['why'])}" if s.get("why") else ""
        out.append("- 衔接：" + ("；".join(anchors) + why if anchors else "不接首尾帧，硬切进入" + (why or "；开场站位按上一段结尾写")) + "\n")
        out.append(f"- 配方：{'武戏（挂 LoRA 链）' if p['kind'] == 'fight' else '文戏（不挂 LoRA）'}专属二采，种子 {sh.get('seed', s.get('seed', get(d, 'defaults.seed', 7100)))}；"
                   f"成片用 {st.get('take') or '—'}，{st.get('note', '待出')}\n\n")
        if p["positions"]:
            out.append(f"**人物站位**：{clean(p['positions']).replace('人物站位：', '', 1)}\n\n")
        out.append("**镜头**\n\n")
        for x in p["shots"]:  # 镜头内的时间码分拍缩进成子列表
            first, *rest = clean(x).split("\n")
            out.append(f"- {first}\n" + "".join(f"  {r}\n" if r.startswith("- ") else f"  {r}\n" for r in rest))
        lines = re.findall(r"<d>(.*?)</d>", " ".join(p["shots"]), re.S)
        lines = [re.sub(r"^\s*\[[^\]]*\]\s*", "", l).strip() for l in lines]
        out.append("\n**台词**：" + ("；".join(f"“{l}”" for l in lines) if lines else "无") + "\n\n")
        out.append(f"**声音**：{clean(p['sound'])}\n")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", help="分段提示词数据文件（yaml）")
    ap.add_argument("--out", help="输出 md 路径（默认：数据文件旁边的 full_script.md）")
    ap.add_argument("--status", help="每段用哪一版、进度的 yaml（可省略）")
    ap.add_argument("--shots", help="shots.json（可省略；带上就在表里写 take 和种子）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    add_config_arg(ap)
    a = ap.parse_args()
    cfg = load_config(a.config)
    try:
        import yaml
        d = B.load_data(a.data)
        status = yaml.safe_load(Path(a.status).read_text(encoding="utf-8")) if a.status else {}
        shots = {s["id"]: s for s in json.loads(Path(a.shots).read_text(encoding="utf-8"))} if a.shots else {}
        doc = build_doc(d, cfg, status or {}, shots)
    except B.DataError as e:
        sys.exit(f"数据错误：{e}")
    for w in sorted(set(B.WARN)):
        print("[警告]", w, file=sys.stderr)
    if a.dry_run:
        print(doc)
        return
    out = Path(a.out) if a.out else Path(a.data).resolve().parent / "full_script.md"
    out.write_text(doc, encoding="utf-8")
    print(f"写入 {out}（{len(doc)} 字，{len(d['segments'])} 段）")


if __name__ == "__main__":
    main()

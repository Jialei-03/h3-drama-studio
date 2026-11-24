#!/usr/bin/env python3
"""出片前的机械检查：读 shots.json（build_shots.py 的输出），把容易踩的坑在排队前拦下来。

脚本里只放通用检查；作者片子专属的规则（右手握剑、座位左右、坑出现的时机……）全部从一份规则 yaml 读，
写法见 examples/gemini-revenge/data/rules.example.yaml。你的故事踩过什么坑，就往规则文件里加什么。

通用检查（错误 E 会让退出码为 1；警告 W 只提示，加 --strict 才算失败）：
  E 段长超过上限（默认 12 秒；武戏 10 秒；带接续 ctx 的段新内容 9.9 秒、含接续帧不超过 260 帧）
  E 提示词里残留 {占位符}，或 <Subject N> 的 N 超过挂的参考图张数
  E 站位里出现的人物/召唤物没有挂参考图（--data 给了数据文件就自动按角色表检查，也可在规则里手写 ref_required）
  E 武戏段的镜头没有时间码；W 最后一个镜头的时间码终点和段长对不上
  E 武戏段里出现招牌大招以外的台词
  W 文戏段写了时间码；W 文戏台词字数超出每秒预算（默认 5 字/秒）
  E 命中禁用词表 banned_words；E 命中规则里的 banned / required / not_before
  E 声明了接续（first/last/ctx）的段，提示词里没写"从锚定画面开始"；没有锚点的段却写了"接续"

用法示例：
  python3 scripts/check_script.py shots.json --rules rules.yaml --data segments.yaml
  python3 scripts/check_script.py shots.json --only f1,f2 --strict

状态：本机用示例数据（含故意写错的用例）验证过各项检查；未在干净环境对真实片子端到端验证。
"""
import argparse
import json
import re
import sys
from pathlib import Path

DEFAULTS = {
    "max_seconds": 12,
    "fight_max_seconds": 10,
    "ctx_max_seconds": 9.9,      # 接续段：新内容秒数上限，16 GB 显存的安全线
    "max_frames": 260,           # 接续段：含 22 帧接续的总帧数上限
    "max_chars_per_second": 5,   # 文戏台词预算：每秒 4–5 个汉字
    "signature_moves": [],
    "banned_words": [],
    "dialogue_no_timecode": True,
    "fight_required_phrases": [],
    "fight_kind_regex": None,
    "anchor": {
        "opening_regex": r"opens exactly on the anchored first frame|opens in the middle of the previous shot",
        "last_regex": r"ends exactly on the anchored last frame",
        "positions_regex": r"Continuing from the previous frame",
    },
}
TC = r"(\d+(?:\.\d+)?)\s*[–—-]\s*(\d+(?:\.\d+)?)\s*(?:s|sec|秒)\b"


def load_rules(path):
    rules = json.loads(json.dumps(DEFAULTS))
    if path:
        try:
            import yaml
        except ImportError:
            sys.exit("缺少 PyYAML：pip install pyyaml")
        user = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(rules.get(k), dict):
                rules[k].update(v)
            else:
                rules[k] = v
    return rules


def frames_for(seconds, ctx_frames=0):
    fr = max(5, round(seconds * 24) + ctx_frames)
    return fr + (5 - fr % 17) % 17


def parts(prompt):
    """把提示词拆成 站位、镜头正文、镜头列表。"""
    m = re.search(r"^\[Shot 1\]", prompt, re.M)
    body_start = m.start() if m else 0
    end = prompt.find("overall_soundscape:")
    body = prompt[body_start: end if end > body_start else len(prompt)]
    pm = re.search(r"Positions:(.*?)(?=^\[Shot 1\])", prompt, re.S | re.M)
    shots = [(int(n), t) for n, t in re.findall(r"^\[Shot (\d+)\](.*?)(?=^\[Shot \d+\]|\Z)", body, re.S | re.M)]
    return (pm.group(1) if pm else ""), body, shots


def lines_of(text):
    out = []
    for raw in re.findall(r"<d>(.*?)</d>", text, re.S):
        out.append(re.sub(r"^\s*\[[^\]]*\]\s*", "", raw).strip())
    return out


def window(text, m, before=80, after=60):
    """命中位置前后各取一小段（到句号/分号为止），用来判断"有没有带限定词"。"""
    a = max(text.rfind(".", 0, m.start()), text.rfind(";", 0, m.start()), m.start() - before)
    b_candidates = [i for i in (text.find(".", m.end()), text.find(";", m.end())) if i != -1]
    b = min(min(b_candidates, default=m.end() + after), m.end() + after)
    return text[max(a, 0): b]


def auto_ref_rules(data_path):
    """从 build_shots 的数据文件按角色表生成规则：站位里写了名字，就必须挂对应图片。"""
    import yaml
    d = yaml.safe_load(Path(data_path).read_text(encoding="utf-8")) or {}
    out = []
    for k, c in (d.get("characters") or {}).items():
        kind = c.get("kind", "person")
        if kind == "scene":
            continue
        nm = c.get("name", k)
        nm = nm.get("en", k) if isinstance(nm, dict) else nm
        if re.match(r"(?i)^the\s", nm):
            nm = nm[4:]
        out.append({"pattern": r"\b" + re.escape(nm) + r"\b", "image": c["image"], "scope": "positions" if kind == "person" else "detail",
                    "message": f"{nm}"})
    return out


def check(shots, rules, auto_refs=()):
    issues = []
    order = {s["id"]: i for i, s in enumerate(shots)}

    def add(sev, sid, msg):
        issues.append((sev, sid, msg))

    kind_re = re.compile(rules["fight_kind_regex"]) if rules.get("fight_kind_regex") else None
    for i, s in enumerate(shots):
        sid, p = s["id"], s["prompt"]
        sec = s["seconds"]
        kind = s.get("kind") or ("fight" if kind_re and kind_re.search(sid) else "dialogue")
        positions, body, shot_blocks = parts(p)
        d0 = p.find("detailed_description:")
        detail = p[d0: p.find("overall_soundscape:") if p.find("overall_soundscape:") > d0 else len(p)] if d0 >= 0 else p  # 风格段、站位、镜头，不含角色定义
        scope = {"positions": positions, "body": body, "detail": detail, "prompt": p}

        # --- 时长 ---
        if sec > rules["max_seconds"]:
            add("E", sid, f"{sec} 秒超过上限 {rules['max_seconds']} 秒")
        if kind == "fight" and sec > rules["fight_max_seconds"]:
            add("E", sid, f"武戏 {sec} 秒超过 {rules['fight_max_seconds']} 秒，要拆段")
        if s.get("ctx"):
            if sec > rules["ctx_max_seconds"]:
                add("E", sid, f"接续段新内容 {sec} 秒超过 {rules['ctx_max_seconds']} 秒")
            fr = frames_for(sec, s.get("ctx_frames", 22))
            if fr > rules["max_frames"]:
                add("E", sid, f"含接续帧共 {fr} 帧，超过 {rules['max_frames']} 帧的安全线（16 GB 显存）")

        # --- 占位符与主体编号 ---
        for m in re.findall(r"\{[^{}]*\}", p):
            add("E", sid, f"残留占位符 {m}")
        nsub = len(s.get("images", []))
        bad = sorted({int(n) for n in re.findall(r"<Subject (\d+)>", p) if int(n) > nsub or int(n) < 1})
        if bad:
            add("E", sid, f"提示词里用了 <Subject {bad}>，但只挂了 {nsub} 张参考图")
        if not shot_blocks:
            add("E", sid, "找不到 [Shot 1]：提示词结构不对")

        # --- 参考图 ---
        have = {Path(x).name for x in s.get("images", [])}
        for r in list(rules.get("ref_required") or []) + list(auto_refs):
            if sid in (r.get("except_ids") or []) or (r.get("ids") and sid not in r["ids"]):
                continue
            text = scope[r.get("scope", "positions")]
            if re.search(r["pattern"], text) and Path(r["image"]).name not in have:
                add("E", sid, f"{r.get('message', r['pattern'])} 出现在{'站位' if r.get('scope', 'positions') == 'positions' else '正文'}里，但没挂参考图 {r['image']}")

        # --- 时间码与台词 ---
        lines = lines_of(body)
        if kind == "fight":
            for n, t in shot_blocks:
                if not re.search(TC, t[:160]):
                    add("E", sid, f"武戏 [Shot {n}] 没有时间码（写成 `0.0–2.5 s.`）")
            ends = [float(m.group(2)) for _, t in shot_blocks[-1:] for m in re.finditer(TC, t)]
            if ends and abs(max(ends) - sec) > 0.6:
                add("W", sid, f"最后一个镜头的时间码终点 {max(ends)} s 和段长 {sec} s 对不上")
            sig = [x.lower() for x in rules["signature_moves"]]
            for l in lines:
                if not any(x in l.lower() for x in sig):
                    add("E", sid, f"武戏里有招牌大招以外的台词：{l[:40]}")
            for ph in rules["fight_required_phrases"]:
                if ph not in p:
                    add("E", sid, f"武戏段缺少必写的句子：{ph}")
        else:
            if rules["dialogue_no_timecode"] and any(re.search(TC, t) for _, t in shot_blocks):
                add("W", sid, "文戏段写了时间码（文戏事件挂在台词和动作上，不写时间码）")
            chars = sum(len(re.sub(r"[\W_]+", "", l)) for l in lines)
            if sec and chars / sec > rules["max_chars_per_second"]:
                add("W", sid, f"台词 {chars} 字 / {sec} 秒 = {chars / sec:.1f} 字/秒，超过 {rules['max_chars_per_second']}")

        # --- 禁用词表 ---
        low = p.lower()
        for w in rules["banned_words"]:
            if w.lower() in low:
                add("E", sid, f"出现禁用词：{w}")

        # --- 规则文件里的 banned / required / not_before ---
        for r in rules.get("banned") or []:
            if (r.get("ids") and sid not in r["ids"]) or sid in (r.get("except_ids") or []) or (r.get("kinds") and kind not in r["kinds"]):
                continue
            text = scope[r.get("scope", "body")]
            for m in re.finditer(r["pattern"], text):
                if r.get("unless") and re.search(r["unless"], window(text, m)):
                    continue
                add("E", sid, f"{r.get('message', r['pattern'])}：…{text[max(0, m.start() - 20): m.end() + 20].strip()}…")
        for r in rules.get("required") or []:
            if (r.get("ids") and sid not in r["ids"]) or sid in (r.get("except_ids") or []) or (r.get("kinds") and kind not in r["kinds"]):
                continue
            if not re.search(r["pattern"], scope[r.get("scope", "prompt")]):
                add("E", sid, f"缺少：{r.get('message', r['pattern'])}")
        for r in rules.get("not_before") or []:
            if r["before"] not in order:
                continue
            if i < order[r["before"]] and re.search(r["pattern"], scope[r.get("scope", "body")]):
                add("E", sid, f"{r.get('message', r['pattern'])}（不能早于 {r['before']}）")

        # --- 衔接锚点 ---
        a = rules["anchor"]
        anchored = [k for k in ("first", "last", "ctx") if s.get(k)]
        for k in anchored:
            v = s[k]
            if isinstance(v, str) and v.startswith("@"):
                key = v[1:].split(":")[0]
                prev = key.rsplit("_t", 1)[0]
                if prev not in order:
                    add("E", sid, f"{k} 指向不存在的段 {prev}")
                elif order[prev] >= i and k != "last":
                    add("W", sid, f"{k} 指向排在它后面的段 {prev}")
        if s.get("first") or s.get("ctx"):
            if not re.search(a["opening_regex"], p):
                add("E", sid, "声明了首帧/接续锚点，但第一镜没写“从锚定画面开始/从上一段中途开始”")
            if a.get("positions_regex") and not re.search(a["positions_regex"], p):
                add("E", sid, "声明了首帧/接续锚点，但站位里没写“接续上一画面”")
        if s.get("last") and not re.search(a["last_regex"], p):
            add("E", sid, "声明了尾帧锚点，但没写“停在锚定的尾帧上”")
        if not anchored and a.get("positions_regex") and re.search(a["positions_regex"], p):
            add("E", sid, "站位写了“接续上一画面”，但这一段没有任何锚点（first/ctx）")
    return issues


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots", nargs="?", default="shots.json", help="shots.json（默认当前目录的 shots.json）")
    ap.add_argument("--rules", help="规则 yaml（项目专属的禁用写法、座位表、招牌大招等）")
    ap.add_argument("--data", help="build_shots.py 的数据文件：按角色表自动检查“站位里的人物是否都挂了参考图”")
    ap.add_argument("--only", help="只检查这几段，逗号分隔的 id")
    ap.add_argument("--strict", action="store_true", help="警告也算失败")
    a = ap.parse_args()
    shots = json.loads(Path(a.shots).read_text(encoding="utf-8"))
    rules = load_rules(a.rules)
    auto = auto_ref_rules(a.data) if a.data else []
    issues = check(shots, rules, auto)
    if a.only:
        keep = set(a.only.split(","))
        issues = [x for x in issues if x[1] in keep]
        shots = [s for s in shots if s["id"] in keep]
    print(f"{len(shots)} 段，合计 {sum(s['seconds'] for s in shots)} 秒；规则文件：{a.rules or '无（只跑通用检查）'}")
    for sev, sid, msg in issues:
        print(f"[{sev}] {sid}: {msg}")
    errs = sum(1 for x in issues if x[0] == "E")
    warns = len(issues) - errs
    print(f"错误 {errs}，警告 {warns}" if issues else "没有发现机械问题")
    sys.exit(1 if errs or (a.strict and warns) else 0)


if __name__ == "__main__":
    main()

"""共用的小模块：读 config.yaml（各脚本 `from _config import ...`，不要各写各的）。

查找顺序：--config 指定的文件 > 环境变量 H3_CONFIG > 当前目录的 config.yaml > 仓库根的 config.yaml。
都没有就返回空 dict（脚本照常运行，缺的项由 need() 报错并提示该填哪个字段）。

    from _config import add_config_arg, load_config, get, need, font_spec
    ap = argparse.ArgumentParser(); add_config_arg(ap); a = ap.parse_args()
    cfg = load_config(a.config)
    fps = get(cfg, "project.fps", 24)
    zh_path, zh_index = font_spec(cfg, "zh")        # 没配置会报错并提示
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def add_config_arg(ap):
    ap.add_argument("--config", help="config.yaml 的路径（默认：$H3_CONFIG、当前目录、仓库根，依次找）")


def load_config(path=None):
    """返回 dict；指定了 path 但文件不存在时直接报错退出。"""
    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            sys.exit(f"找不到 config 文件：{p}")
        cands = [p]
    else:
        cands = [Path(os.environ["H3_CONFIG"]).expanduser()] if os.environ.get("H3_CONFIG") else []
        cands += [Path.cwd() / "config.yaml", REPO_ROOT / "config.yaml"]
    for p in cands:
        if p.is_file():
            try:
                import yaml
            except ImportError:
                sys.exit("缺少 PyYAML：pip install pyyaml")
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def get(cfg, dotted, default=None):
    """get(cfg, 'project.fps', 24)；路径上任何一层缺失或为空串都返回 default。"""
    cur = cfg
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return default if cur in (None, "") else cur


def need(cfg, dotted, hint=""):
    """必填项：没配置就报错退出，并告诉用户去 config.yaml 填哪一项。"""
    v = get(cfg, dotted)
    if v is None:
        sys.exit(f"config.yaml 里没有 {dotted}。{hint}\n（复制 config.example.yaml 为 config.yaml 后填写，或用命令行参数指定）")
    return v


def font_spec(cfg, name, cli_path=None, cli_index=None, hint=""):
    """字体：返回 (文件路径, 字体集序号)。命令行优先，其次 config 的 fonts.<name> 和 fonts.<name>_index。
    .ttc 字体集需要序号（例：苹方的 Regular 是其中一个序号），.ttf/.otf 用 0。
    路径里也可以写成 `文件#序号`。没配置就报错，不提供任何系统字体默认值。"""
    path = cli_path or get(cfg, f"fonts.{name}")
    if not path:
        sys.exit(f"没有配置字体 fonts.{name}。{hint}请在 config.yaml 的 fonts.{name} 填字体文件路径，或用命令行参数指定。")
    idx = cli_index if cli_index is not None else get(cfg, f"fonts.{name}_index", 0)
    path = str(path)
    if "#" in path:
        path, _, i = path.rpartition("#")
        idx = int(i)
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        sys.exit(f"字体文件不存在：{path}")
    return path, int(idx)

# H3 Drama Studio

一张 16 GB 显卡，从剧本到成片：本地 AI 短剧的一站式 Claude Code skills（MiniMax H3 + ComfyUI）。

> 状态：初版。skills、脚本、模板、案例、工作流和模型下载表都已齐。后期脚本用真实片段跑过；队列脚本生成的工作流和作者主机实际提交的逐节点一致，但重写后的脚本本身还没有向真实的 ComfyUI 提交过任务；出图脚本只做过不联网的试运行。

经验的优先顺序：**故事 > 提示词 > 工作流 > 模型**。

## 生成片段

下面两段都是成片里实际用的版本：没有超分、没有配乐、没有字幕，声音和台词是模型一起生成的。原片 1536×864、24 fps，这里压成了 720p 和动图。

| 文戏 | 武戏 |
|---|---|
| ![文戏示例](assets/dialogue.gif) | ![武戏示例](assets/fight.gif) |
| 9.9 秒，一次生成，用时 20 分钟 | 9.4 秒，由两次生成的镜头拼成，每次生成约 27 分钟 |
| 不挂 LoRA | 挂武戏 LoRA 链 |
| [带声音的 MP4](assets/dialogue.mp4) | [带声音的 MP4](assets/fight.mp4) |

完整成片《Gemini的复仇！》（3 分 44 秒）已发布在抖音、小红书和 B 站，搜索片名即可找到。

## 我的配置

| | |
|---|---|
| 显卡 | RTX 5060 Ti 16 GB |
| 内存 | 96 GB |
| 系统 | Windows，ComfyUI |
| 剪辑和后期 | 另一台 Mac，通过 SSH 连主机（同一台机器上做也可以） |

## 最低配置

只有上面这一套配置是实测过的。下面的最低配置是按模型体积推算的，**没有在更低的机器上验证过**。

| | 最低（推算） | 说明 |
|---|---|---|
| 显存 | 16 GB | 实测可用。12 GB 没试过；二采阶段在 16 GB 上已经接近上限 |
| 内存 | 32 GB | 主模型约 20 GB，文本编码器约 25 GB，都是量化后的体积。作者判断 32 GB 够用，但模型加载和切换会比大内存慢。作者本机是 96 GB，没有在 32 GB 上实测 |
| 硬盘 | 100 GB 空闲，固态 | 模型约 60 GB，其余留给成片和中间文件 |
| 显卡型号 | NVIDIA | 配方里的量化格式和加速算子依赖 CUDA |

## 生成时间参考

全部来自这台机器的队列记录，分辨率 1536×864（一采 1024×576，潜空间放大 1.5 倍后二采），24 fps。

| 类型 | 每秒成片的生成用时 | 10 秒一段 |
|---|---:|---:|
| 文戏（不挂 LoRA） | 1.5–2 分钟 | 15–21 分钟 |
| 武戏（挂 LoRA 链） | 2.4–2.7 分钟 | 24–27 分钟 |

- 用时和片长大致成正比，把一段切短并不省总时间。
- 武戏每段开头有 22 帧（约 0.9 秒）是用来接上一段的，拼接时剪掉，这部分时间也算在内。
- 整个项目的账：成片 3 分 44 秒，由 24 段留用片段拼成；包括所有试验和重渲在内，一共生成了 281 段，显卡累计运行约 84 小时。大部分时间花在反复改提示词上，而不是模型慢。

## 这里有什么

| skill | 管什么 |
|---|---|
| [ai-drama](skills/ai-drama/SKILL.md) | 总入口：12 个环节怎么走 |
| [local-ai-workstation](skills/local-ai-workstation/SKILL.md) | 部署与运维 |
| [h3-video](skills/h3-video/SKILL.md) | MiniMax H3 配方、队列、评测 |
| [drama-preproduction](skills/drama-preproduction/SKILL.md) | 故事、定妆、剧本、状态表、审稿 |
| [drama-scenes](skills/drama-scenes/SKILL.md) | 文戏方案、武戏方案、衔接、验片 |
| [drama-postproduction](skills/drama-postproduction/SKILL.md) | 粗剪、拼接、冲击帧、字幕、配乐 |
| [drama-publish](skills/drama-publish/SKILL.md) | 封面、文案、交付 |

另有 [scripts/](scripts/README.md)、[templates/](templates/README.md) 和一个完整案例 [examples/gemini-revenge/](examples/gemini-revenge/README.md)。

## 现成的工作流和模型地址

- **工作流**：[workflows/](workflows/README.md) 里是作者出这部片时实际提交给 ComfyUI 的工作流，文戏、带接续的文戏、武戏各一份，另有一份给队列脚本用的基础工作流。全部是 ComfyUI 内置节点，放好模型和参考图就能跑。
- **模型**：[模型下载表](skills/local-ai-workstation/references/models.md) 列出了全部 10 个模型文件的文件名、大小、放哪个目录和魔搭（ModelScope）地址，国内可以直连下载。必需的 5 个约 55 GB，武戏 LoRA 5 个约 1.9 GB。

工作流的二采结构、接续方法和 LoRA 搭配学自几位创作者，出处写在 [workflows/README.md](workflows/README.md) 和下面的致谢里。

## 安装

### 方式一：作为 Claude Code 插件安装

在 Claude Code 里用 `/plugin` 添加本仓库（仓库根的 `.claude-plugin/plugin.json` 是插件清单）。具体的子命令和参数**以 Claude Code 官方文档为准**，这里不重复，免得过时。装好后 7 个 skill 一起可用。

### 方式二：把 skill 复制到 `~/.claude/skills/`

```bash
git clone <本仓库地址> h3-drama-studio && cd h3-drama-studio
mkdir -p ~/.claude/skills && cp -r skills/* ~/.claude/skills/
```

- 也可以只复制某一个（例：`cp -r skills/drama-scenes ~/.claude/skills/`）。但 skill 之间用相对路径互相链接（例如 `../../h3-video/references/recipes.md`），只装一个会让指向别的 skill 的链接失效，建议整个 `skills/` 一起复制。
- skill 里提到的 `scripts/`、`templates/`、`examples/` 在仓库根目录，不在 `skills/` 里：保留克隆下来的仓库，在仓库根目录里运行脚本，模板直接从 `templates/` 复制。

### 填写配置

```bash
cp config.example.yaml config.yaml    # config.yaml 已在 .gitignore 里，不会被提交
```

打开 `config.yaml`，按注释填写：出片主机的 SSH 别名和 ComfyUI 地址（`host`）、模型库里的文件名（`models`）、出图服务的模型名（`image_api`）、片子的工作目录和分辨率（`project`）、字幕字体文件的路径（`fonts`）。**密钥不要写进文件**：`image_api` 里只写环境变量的名字，把真正的地址和密钥放在环境变量里（默认 `IMAGE_API_BASE`、`IMAGE_API_KEY`）。脚本按"`--config` 参数 > 环境变量 `H3_CONFIG` > 当前目录 > 仓库根"的顺序找 `config.yaml`。

### 安装脚本的依赖

| 依赖 | 用来做什么 | 怎么装 |
|---|---|---|
| ffmpeg 和 ffprobe（要在 PATH 里） | 拼接、剪帧、重建音轨、字幕、配乐、封面嵌入 | macOS：`brew install ffmpeg`；Debian/Ubuntu：`sudo apt install ffmpeg`；Windows：从 ffmpeg 官网下载并加进 PATH |
| Python 3 和 `numpy`、`Pillow`、`PyYAML` | 所有脚本 | `pip install numpy pillow pyyaml` |
| `mlx-whisper`（Apple 芯片）或 `openai-whisper` | 可选：验片时听写台词、给字幕对时间 | `pip install mlx-whisper` 或 `pip install openai-whisper` |

装完用 `ffmpeg -version` 和 `python3 scripts/check_script.py --help` 检查一下。出片主机上的 ComfyUI、模型和文本大模型不在本仓库里，部署见 [local-ai-workstation](skills/local-ai-workstation/SKILL.md)；本仓库不含任何模型、音乐或第三方工作流文件。

## 致谢

本仓库的配方和方法学自多位创作者公开分享的视频、教程和工作流。这里只写学到了什么，不收录他们的提示词原文，不分发他们的工作流、整合包或模型文件；要用请去原作者那里取，并遵守他们的使用条款。配方每一项出自哪里、本仓库改了什么，见 [credits.md](skills/h3-video/references/credits.md)。

- **吃猪侠233**：现用配方的主要来源（15 步无 LoRA 画质增强流和"专属二采"的整体结构），以及"差距在参考图和提示词，不为加速牺牲画质"的立场。链接：[B 站主页](https://space.bilibili.com/111985620)
- **金鱼**：二采的节点框架思路，DMAD 融合 LoRA 加 MysticXXX 的武戏链和速度滑块，人物参考图带大脸特写的做法。链接：[B 站主页](https://space.bilibili.com/14843708)，[终极篇视频](https://www.bilibili.com/video/BV1LKJm6VELc)
- **惊尘**：上下文接续（上一段末尾 22 帧加音频锚在第 0 帧）和接缝色差匹配，武戏逐段接续的基础。链接：[B 站主页](https://space.bilibili.com/30070651)，[上下文接续方案视频](https://www.bilibili.com/video/BV11kHs6NEef)
- **WorkFisher**：短剧全流程、多图参考，以及方位用画面坐标、一个镜头只点一个主体的提示词写法。链接：[B 站主页](https://space.bilibili.com/17919458)，[GitHub](https://github.com/Work-Fisher/AIFISHER)
- **凌大壮**：AI 冲击帧教程，后期冲击帧的做法来自这里。链接：[冲击帧教程视频](https://www.bilibili.com/video/BV1FGHw6bEKM)
- **MiniMax**：H3 视频提示词写作指南和 ComfyUI 官方 H3 教程。链接：[MiniMax-AI/MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3)（提示词 skill 在仓库的 `skills/` 目录）
- **模型和 LoRA 的作者**：Cobijada Hybrid 底模（Winnougan）、Mystic XXX（alcaitiff，来历见 [lora.md](skills/h3-video/references/lora.md) 的披露）、H3_Combat_V2 和 Motion_Repair_V2（四只兔子）、潜空间放大模型（LBH-123-AI）等，名单见 credits.md。

## 许可

代码 MIT，文档 CC BY 4.0，见 [LICENSE](LICENSE)。本仓库不包含任何模型文件和音乐。`workflows/` 里是作者自己出片用的工作流，方法的出处见该目录的说明。

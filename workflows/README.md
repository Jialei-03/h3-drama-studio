# workflows

作者出这部片时**实际提交给 ComfyUI 的工作流**，API 格式，全部是 ComfyUI 内置节点（作者用的是 ComfyUI 0.45），不需要装自定义节点。

这几份不是事后重搭的：ComfyUI 保存视频时会把当时提交的整份工作流写进 mp4 的元数据，这里的文件是从成片里读出来的，只改了三样东西：参考图和接续视频的文件名换成了通用名字、保存路径的前缀、给每个节点加了中文标题。采样参数、模型文件名、种子、提示词都是原样。

| 文件 | 用途 | 节点数 | 出自成片的哪一段 |
|---|---|---:|---|
| [h3_dialogue.api.json](h3_dialogue.api.json) | **文戏**：专属二采，不挂 LoRA，3 张参考图 | 32 | 开打前的对话 |
| [h3_dialogue_continue.api.json](h3_dialogue_continue.api.json) | **接在上一段后面的文戏**：同上，另加上一段末尾 22 帧的接续 | 37 | 战后第一段对话（首页的文戏示例） |
| [h3_fight_continue.api.json](h3_fight_continue.api.json) | **武戏**：专属二采 + 5 个 LoRA 的武戏链 + 22 帧接续，4 张参考图 | 43 | Supernova 大招（首页武戏示例的前 2 秒） |
| [h3_base.api.json](h3_base.api.json) | **基础工作流**：只有一采的 16 个节点，给 `scripts/drama_queue.py` 当底子用 | 16 | 从上面的文戏工作流里取出基础部分 |

## 怎么用

**直接用（手动出一段）**

1. 按 [模型下载表](../skills/local-ai-workstation/references/models.md) 把模型放进 ComfyUI 的模型目录。文件名和工作流里写的不一样时，改工作流里对应节点的文件名。
2. 把你的参考图放进 ComfyUI 的 `input/` 目录，文件名用 `char_a.png`（人物 A 定妆图）、`char_b.png`（人物 B 定妆图）、`scene.png`（场景图）、`summon.png`（召唤物图，只有武戏那份用到）。
3. 带接续的两份还需要 `prev_tail_22f.mp4`：上一段成片的最后 22 帧连同声音，放进 `input/`。可以用 ffmpeg 截，例：`ffmpeg -sseof -0.9167 -i 上一段.mp4 -frames:v 22 -c:v libx264 -crf 12 -c:a aac prev_tail_22f.mp4`。
4. 把 json 拖进 ComfyUI 的界面，改"参考生视频"节点里的提示词，运行。也可以把 json 包成 `{"prompt": ...}` 直接 POST 到 ComfyUI 的 `/prompt` 接口。
5. 输出两个视频：`h3-drama/xxx` 是二采后的成片（1536×864），`h3-drama/xxx_stage1` 是一采预览（1024×576）。

里面带着作者当时的提示词，可以先原样跑通，再换成你自己的。提示词怎么写见 [drama-scenes](../skills/drama-scenes/SKILL.md)。

**批量用（队列）**

`config.example.yaml` 默认指向 `h3_base.api.json`，节点对应表已经填好。`scripts/drama_queue.py` 会按每条 shot 的设置，在它上面自动加 LoRA 链、SigmaShift、二采、接续这些节点。脚本生成的工作流和上面三份里的两份逐节点对照过，结构和参数完全一致。用法见 [queue.md](../skills/h3-video/references/queue.md)。

## 关键参数

| 环节 | 设置 |
|---|---|
| 一采 | 1024×576，手写 10 步 sigma，euler，SigmaShift 视频 12、音频 3，稀疏注意力 |
| 放大 | 潜空间放大模型，放大到 1536×864（宽高必须是 32 的倍数） |
| 二采 | beta 调度 14 步，从第 8 步切开只跑后 6 步，euler，与一采同一个种子 |
| 帧数 | 24 fps；10 秒左右是 243 或 260 帧（接续段含开头 22 帧） |
| 接续 | 上一段末尾 22 帧加声音锚在第 0 帧；二采时要在放大后的潜变量上重新加一次锚点 |

为什么这样设、试过哪些别的方案，见 [recipes.md](../skills/h3-video/references/recipes.md) 和 [tried-and-dropped.md](../skills/h3-video/references/tried-and-dropped.md)。

## 出处

这套工作流是作者把几位创作者公开分享的方法组合起来的，不是原创的采样方案：

- **专属二采的整体结构**（一采 10 步 → 潜空间放大 → 二采在第 8 步切开、SigmaShift 12/3）来自 [吃猪侠233](https://space.bilibili.com/111985620)。作者把放大倍数从他的 1.8 改成了 1.5，一采分辨率从 1056×608 改成了 1024×576，为的是在 16 GB 显卡上跑得动。
- **二采的节点框架和武戏 LoRA 链的搭配**来自 [金鱼](https://space.bilibili.com/14843708) 的"终极篇"。
- **上下文接续**（上一段末尾 22 帧加声音锚在第 0 帧）来自 [惊尘](https://space.bilibili.com/30070651)。
- **一采的 10 步 sigma 曲线**来自 RunningHub 上公开的 H3 工作流。
- 模型和 LoRA 各自的作者见 [模型下载表](../skills/local-ai-workstation/references/models.md) 和 [credits.md](../skills/h3-video/references/credits.md)。

想要原作者的完整工作流和整合包，请去他们的主页取。

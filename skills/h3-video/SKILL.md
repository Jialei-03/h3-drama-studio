---
name: h3-video
description: MiniMax H3 视频生成的模型与采样配方：底模和文本编码器怎么选、单采与二采、文戏配置和武戏配置、LoRA 搭配、批量出片队列与通宵运行、怎样公平地比较画质，以及试过后放弃的方案。在选工作流或 LoRA、改步数和分辨率、排队出片、暂停或恢复队列、比较两种配置的画质时使用。MiniMax H3 video recipes on ComfyUI: base model, sampler, two-stage upscale, LoRA chains, batch queue, quality evaluation.
---

# MiniMax H3 出片：模型、配方、队列、评测

在一张 RTX 5060 Ti 16 GB 上，用 ComfyUI 跑 MiniMax H3 做短剧，每一段怎么配、怎么排队、怎么比。部署和环境看 [local-ai-workstation](../local-ai-workstation/SKILL.md)；写镜头和提示词看 drama-scenes。

## 先选配方：这一段是什么戏

| | 文戏（对白、表演、反应） | 武戏（打斗、特效对轰） |
|---|---|---|
| 采样 | 专属二采 | 专属二采 |
| 一采 | 1024×576，10 步，euler | 同左 |
| 放大与二采 | 潜空间 ×1.5 到 1536×864；beta 14 步，第 8 步切开，跑后 6 步，euler | 同左 |
| LoRA | **一个都不挂** | 五个的链：融合 DMAD 0.8、MysticXXX 0.35、速度滑块 3、H3_Combat_V2 0.65、Motion_Repair_V2 0.35 |
| 接续 | 站位对上就硬切 | 接上一段末尾 22 帧加音频，一次只渲一段 |
| 每秒成片耗时 | 约 1.5–2 分钟 | 约 2.4–2.7 分钟 |
| 10 秒一段 | 约 15–20 分钟 | 约 24–27 分钟 |

耗时是队列记录的墙钟时间，含每段模型加载；分辨率 1536×864、24 fps；用时与片长大致成正比，切短一段不省总时间。可信度：两套配置都是已验证（多次出片、作者看原片认可）。每个 LoRA 各自的贡献没有做过消融，标未验证。

共同项：Cobijada Hybrid 底模、Qwen3-VL 32B int8 普通编码器、Sol 稀疏注意力开、SigmaShift 视频 12 音频 3、CFG 1、参考图尺寸 `match`、帧数 `17k+5`。具体参数、二采的接线和 `shots.json` 写法见 [recipes.md](references/recipes.md)。

## 必须遵守的规则

1. **文戏、武戏都用专属二采，不用单采。**
   为什么：2026-11-19 同提示词、同种子、同首帧的对照里，作者看片认为二采更好，单采还更慢（26 分钟对 16 分钟）。早期"单采最好"的结论已作废。
2. **文戏不挂任何 LoRA；武戏链只给武戏段。**
   为什么：打戏后的对白段挂了 LoRA，作者看片觉得比打戏前不挂的更糊。
3. **二采宽高必须是 32 的倍数。**
   为什么：1584×912 在二采报 shape 错误；1536×864 可以。
4. **有首帧、末帧或接续锚点时，二采要在放大后的潜空间上重新加一次，并单独建一个 guider。**
   为什么：锚点按一采潜空间的尺寸写进条件，放大后不重加会报 `shape mismatch`。
5. **帧数取 `17k+5`。** 脚本向上取整，自己搭工作流时也要遵守。
6. **改了提示词要换 take 号。**
   为什么：队列用 `id` 加 `take` 判断一段是否出过，不换号就不会重渲。
7. **每条 shot 都写全配方字段。**
   为什么：没写的字段沿用你工作流里已有的值，不一定是现在的配方（原版脚本会落到早期的 15 步单采）。`scripts/build_shots.py` 会替你写全。
8. **比画质只看原片，且同提示词、同种子、同首帧，一次只改一个变量。**
   为什么：缩略图抹掉噪点；固定不全就分不清差异来自哪里。详见 [quality-eval.md](references/quality-eval.md)。
9. **不拿低分辨率的单次采样下结论。**
   为什么：Turbo 类 LoRA 针对 768p 训练，960×544 只适合做草稿。
10. **照抄别人的工作流时，沿连线追到每个参数的真值。**
    为什么：作者最初照抄时把放大倍数和一采分辨率抄错，节点上显示的 1.5 是摆设。
11. **暂停时先建 STOP，再中断当前任务，再 `/free`。**
    为什么：顺序反了，队列会马上提交下一段；ComfyUI 不会自己释放显存。
12. **换队列脚本用"建 STOP、等 `queue stop`、覆盖、重启"，不要杀进程。**
    为什么：杀进程后 ComfyUI 里的任务还在跑，重启会把同一段再提交一次。
13. **要不要用去限制版本，由使用者自己决定。** 见 [uncensor.md](references/uncensor.md)。武戏链里的 MysticXXX 来历特殊，披露见 [lora.md](references/lora.md)。

## 常见问题怎么走

| 你遇到的事 | 去哪里 |
|---|---|
| 文戏或武戏该用哪套参数，shots.json 怎么写 | [recipes.md](references/recipes.md) |
| 武戏链每个 LoRA 管什么，怎么做同提示词同种子的 LoRA 对比 | [lora.md](references/lora.md) |
| 排队、暂停、续跑、换脚本、通宵、早上检查、释放显存 | [queue.md](references/queue.md) |
| 把自己的工作流接到队列脚本（导出 API json、填映射表、二采和接续怎么接进图里、有哪些限制） | [queue.md](references/queue.md) 末节“接入你自己的工作流” |
| 比两个配置谁画质好、辅助指标怎么用 | [quality-eval.md](references/quality-eval.md) |
| 想试单采、33 步、超分、关键帧、Pika 之类之前 | [tried-and-dropped.md](references/tried-and-dropped.md) |
| 去限制版本的客观说明 | [uncensor.md](references/uncensor.md) |
| 这些做法是谁想出来的 | [credits.md](references/credits.md) |
| 装环境、放模型、torch 版本、远程连接、下载模型 | [local-ai-workstation](../local-ai-workstation/SKILL.md) |

## 依赖的脚本与配置

| 要用的 | 在哪 |
|---|---|
| 出片队列（读你自己导出的工作流和 `workflow:` 映射表） | `scripts/drama_queue.py run`，接入方法见 [queue.md](references/queue.md) 末节 |
| 武戏接续的剪接和颜色匹配 | `scripts/chain_join.py` |
| 验片：切点、台词听写 | `scripts/review_ep.py`、`scripts/asr.py` |
| 主机、端口、模型文件名、工作流映射 | `config.yaml`：`host.comfyui_url`、`host.queue_dir`、`host.comfyui_input`、`host.comfyui_output`、`models.unet`、`models.text_encoder`、`models.latent_upscaler`、`models.fight_loras`、`recipe`、`workflow` |

## 可信度约定

- **已验证**：多次出片确认。
- **单次实测**：一次对照的结果，换个种子或镜头可能不同。
- **未验证**：推算、他人报告或没试过。

数字都带条件：RTX 5060 Ti 16 GB、1536×864、24 fps、10 秒左右的片段。换显卡或换分辨率要重测。

---
name: local-ai-workstation
description: 在一台 16 GB 显存级别的 Windows 主机上部署和维护本地 AI：ComfyUI 与 MiniMax H3 视频模型、可选的本地文本大模型，显卡在两者之间切换，从另一台电脑远程连接，以及在国内网络下直连下载模型。在需要装环境、放模型、启动或切换服务、排查变慢或启动失败、远程连接主机、下载大模型时使用。Deploy and operate a local AI box (ComfyUI + MiniMax H3, optional local LLM) on a 16 GB GPU: setup, GPU hand-off, remote access, model downloads.
---

# 本地 AI 主机：部署与运维

一台 Windows 主机、一张 16 GB 显卡，做两类事：**视频生成**（ComfyUI + MiniMax H3，必需）和**文本推理**（本地大模型，可选）。出片配方在 [h3-video](../h3-video/SKILL.md)，本 skill 管它底下的机器和环境。

作者的实测配置是 RTX 5060 Ti 16 GB + 96 GB 内存。最低配置是推算的，**没有验证过**，见 [hardware.md](references/hardware.md)。

## 要做的事 → 看哪里

| 要做的事 | 看哪里 |
|---|---|
| 判断我的机器能不能跑、该升级什么 | [hardware.md](references/hardware.md) |
| 装 ComfyUI、放模型、选 torch 的 CUDA 版本、新旧版本并排 | [comfyui-setup.md](references/comfyui-setup.md) |
| 每个模型文件去哪下载（魔搭地址、大小、放哪个目录） | [models.md](references/models.md) |
| 在同一张卡上跑本地文本模型（可选） | [llm-basalt.md](references/llm-basalt.md) |
| 从另一台电脑用 SSH 或 Tailscale 连主机 | [remote-access.md](references/remote-access.md) |
| 在国内下载大模型、代理软件开着 TUN 模式 | [china-network.md](references/china-network.md) |
| 启动失败、突然变慢、显存不够、结果不对 | [pitfalls.md](references/pitfalls.md) |
| 出片配方、队列、LoRA、画质对比 | [h3-video](../h3-video/SKILL.md) |

## 必须遵守的规则

1. **文本模型和视频模型不能同时占用显卡，切换前先卸载另一边。**
   为什么：16 GB 不够两边同时放。ComfyUI 出完片不会自己释放显存，约 13 GiB 一直占着，这时加载文本模型会因显存不足缩小专家缓存，变慢。
   做法：视频 → 文本，先对 ComfyUI 发 `POST /free`，body 为 `{"unload_models": true, "free_memory": true}`，再用 `nvidia-smi` 确认；文本 → 视频，先卸载文本模型。
2. **动手之前先读运行中的服务状态，再信文档。**
   为什么：机器经过多轮调整，文档会落后于实际。
   做法：`nvidia-smi` 看谁占着显卡，ComfyUI 的 `/system_stats` 和 `/queue`，文本服务的 `/health`。
3. **下载大文件前先报体积，并确认走的是直连；下完校验 SHA-256。**
   为什么：作者的代理流量因大下载被耗尽过两次，下载器的"不走代理"参数在代理软件开着 TUN 模式时不起作用。
   做法：1 字节请求加代理日志，见 [china-network.md](references/china-network.md)。优先魔搭 ModelScope。
4. **删除大文件前逐项向用户确认；不动不认识的大文件。**
   为什么：磁盘紧张，误删的模型要重新下载，而且可能是别的程序的虚拟磁盘或交换文件。
5. **模型一律放实体文件，不用符号链接。**
   为什么：作者早期的链接指向别的软件的工作目录，目录被清理后模型就找不到了。
6. **PyTorch 的 CUDA 版本必须与显卡匹配，装完立刻自检。**
   为什么：作者的 50 系显卡上 `cu128` 会让优化算子被静默关闭，同卡慢一倍，不报错（单次实测）；`cu130` 正常。
7. **测速和比较时不碰主机，同时段交替跑。**
   为什么：主机上有下载、拷贝或通过 SSH 读文件，速度会掉一半；闲置后的第一组也偏慢；不同时段有 3–7% 漂移。
8. **长跑进程不要靠 SSH 会话保活。**
   为什么：会话一断，里面启动的进程就被杀。常驻服务用桌面快捷方式启动，远程启动长跑进程用 WMI 创建进程，见 [remote-access.md](references/remote-access.md)。
9. **主机通过 SSH 访问时，别把没有 API key 的服务开到公网。**
   为什么：文本服务通常没有 key；ComfyUI 的入口可以上传文件、操作队列。只放行自己的设备。
10. **改了配置就实际验证，再告诉用户。**
    做法：改了环境，出一段短片（960×544、90 帧）确认能出片、有声音，只用它判断"能不能跑"，不判画质。改了文本服务，重新加载并跑一次请求，用 `/v1/status` 的 `last_timings` 和引擎日志确认生效。
11. **测得的数字连同条件一起记下来。** 条件包括模型、分辨率、帧数、种子、冷热状态、显卡是否被占用。

## config.yaml 里和本 skill 相关的项

| 变量 | 含义 |
|---|---|
| `host.ssh` | 主机的 SSH 别名或 `用户@地址`；出片和剪辑在同一台机器上就留空 |
| `host.comfyui_url` | ComfyUI 的地址，新旧版本端口不同，指向新版 |
| `host.comfyui_output` | 主机上 ComfyUI 的 output 目录 |
| `host.queue_dir` | 主机上放 `shots.json`、`results.json` 的目录 |
| `models.unet`、`models.text_encoder`、`models.latent_upscaler`、`models.fight_loras` | 你模型库里的文件名 |

主机地址、用户名、密钥都只写在你本机的 `config.yaml` 和 `~/.ssh/config` 里，`config.yaml` 在 `.gitignore` 中，不会被提交。

## 日常使用的最短路径

| 目的 | 做法 |
|---|---|
| 出视频 | 确认文本模型已卸载；启动新版 ComfyUI；用 `scripts/drama_queue.py` 排队出片 |
| 出完视频想用文本模型 | `POST /free`，确认显存降下来，再加载文本模型 |
| 从另一台电脑操作 | `ssh <host.ssh>`，或 `ssh -N -L` 把端口转发到本机 |
| 装新模型 | 先报体积，直连下载，校验 SHA-256，放进模型库对应目录 |
| 某件事突然变慢 | 先查 [pitfalls.md](references/pitfalls.md)，不要先怀疑硬件 |

## 可信度约定

- **已验证**：作者多次出片或多次测量确认。
- **单次实测**：一次测量的结果，换条件可能不同。
- **未验证**：推算、他人报告或没试过。最低配置整体属于未验证。

数字都带条件：RTX 5060 Ti 16 GB、Windows 11、ComfyUI 0.45、2026-11。换显卡、驱动或软件版本，要重测。

# ComfyUI 安装与模型放置

什么时候读：第一次在一台 Windows 主机上装 ComfyUI 跑 H3，或者出片时报缺节点、缺模型、变慢一倍之后回来对照环境。

下面的版本号和数字是作者 2026-11 的环境（RTX 5060 Ti 16 GB，Windows）。主机、端口和模型文件名在你的 `config.yaml` 里填：`host.comfyui_url`、`models.unet`、`models.text_encoder`、`models.latent_upscaler`。

## 目录布局（示意）

```text
<AI 根目录>/
  python-env/       一个 Python 环境，装 torch，新旧两个 ComfyUI 共用
  models/           唯一的模型库
  comfyui-new/      ComfyUI 0.45，出片和队列用，允许自定义节点
  comfyui-old/      ComfyUI 0.37（可选），只用内置节点，手动点工作流用
  overlay/          新版多出来的依赖，单独放
  queue/            shots.json、results.json、queue.log（即 host.queue_dir）
```

## 为什么新旧两个版本并排

新版（0.45）带有 H3 二采要用的内置节点：潜空间放大、`SplitSigmas`、上下文窗口等。旧版（0.37）已经稳定，作者让它保持只用内置节点（启动参数加 `--disable-all-custom-nodes`），用来手动点工作流。并排装而不是原地升级，是为了不动已经能用的那个。

- 两个版本用**不同的端口**；`host.comfyui_url` 指向新版，别让队列连错。
- 两个版本**共用同一个模型库和同一个 Python 环境**，模型只下载一份。用 ComfyUI 自带的启动参数指向它：`--models-directory <模型库>`，或 `--extra-model-paths-config <yaml>`。这两个参数都在 0.45 的参数表里；作者具体用了哪一种，没有记录。
- 新版比旧版多出几个依赖。把它们装进一个单独目录，只在新版的启动脚本里让 `PYTHONPATH` 指向它，旧版就不受影响。作者为 0.45 装的是（`--no-deps`，`--target <overlay>`）：`comfy-kitchen==0.2.35`、`comfy-aimdo==0.5.5`、`comfy-angle`、`comfyui-frontend-package==1.52.7`。版本要和你装的 ComfyUI 的 `requirements.txt` 对应，别照抄。

## PyTorch 必须和显卡匹配的 CUDA 版本

作者的 50 系显卡上用 `torch 2.13.0+cu130`。**换成 `cu128`，优化算子会被静默关闭，同一张卡慢一倍**，而且不报错、不警告（单次实测）。装好以后立刻检查，不要等到出片慢了才发现：

```powershell
$env:PYTHONPATH = "<overlay>"
& <python-env>\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))"
& <python-env>\python.exe -c "import torch, comfy_kitchen as c; print(c.sol_attn_is_available(torch.device('cuda:0')))"
```

第二条应打印 `True`。出片时日志里应出现 `sparse producer path`，说明稀疏注意力在起作用。分辨率或时长变小后，token 数可能低于 12,288 的门槛，此时稀疏注意力不会启用，这是正常的。别的显卡该选哪个 CUDA 版本，以 PyTorch 官网和你的驱动为准（作者没有测过别的卡，未验证）。

国内装 pip 包用镜像，见 [china-network.md](china-network.md)。

## 模型放哪里

以下是 ComfyUI 的默认目录名，都在模型库下。文件名以你下载到的为准，填进 `config.yaml`。

| 角色 | 公开名 | 目录 | config 变量 | 大小 |
|---|---|---|---|---:|
| 主模型 | Cobijada Hybrid（int8，剪枝混合版） | `diffusion_models/` | `models.unet` | 约 19.5 GB |
| 文本编码器 | `qwen3vl_32b_minimax_h3_int8_convrot` | `text_encoders/` | `models.text_encoder` | 约 25.3 GB |
| 视频 VAE | `minimax_h3_video_vae_fp16` | `vae/` | | 未记录 |
| 音频 VAE | `minimax_h3_audio_vae_fp32` | `vae/` | | 未记录 |
| 潜空间放大模型 | `minimax_h3_latent_upscaler_3d_conv_v1_fp16` | `latent_upscale_models/` | `models.latent_upscaler` | 约 0.64 GB |
| 武戏 LoRA | 见 h3-video 的 lora.md | `loras/` | `models.fight_loras` | 未记录 |
| 参考图、首帧 | 你自己的图 | ComfyUI 的 `input/` | | |

每个文件的魔搭下载地址见 [models.md](models.md)；怎样在国内确认是直连，见 [china-network.md](china-network.md)。本仓库不分发任何模型文件。现成的工作流在仓库根的 `workflows/`。

### 模型必须是实体文件，不要用符号链接

作者早期把 25.3 GB 的编码器和一个 LoRA 做成指向另一个软件工作目录的符号链接，后来那个目录要清理，才复制成实体文件并逐个校验 SHA-256。教训：链接指向的目录一旦被清理、移动或换盘，ComfyUI 就找不到模型。新模型一律直接放进模型库。

## 工作流与队列

队列脚本用 ComfyUI 的 HTTP 接口提交 API 格式的工作流，用到的内置节点有：`MiniMaxH3ReferenceToVideo`、`MiniMaxH3AddGuide`、`MiniMaxH3SigmaShift`、`MiniMaxH3LatentUpscaleWithModel`、`LatentUpscaleModelLoader`、`SplitSigmas`、`LTXVSeparateAVLatent`、`LTXVConcatAVLatent`、`SamplerCustomAdvanced`、`BasicScheduler`、`LoraLoaderModelOnly`。它还需要一份作为底图的工作流：**用你自己的 H3 工作流，在 ComfyUI 里“导出 (API)”得到 json**，再在 `config.yaml` 的 `workflow:` 里填路径和“角色 → 节点编号”映射表，脚本按表改写节点（原版脚本把一份第三方工作流的节点编号写死在代码里，那份文件不能随仓库分发）。接法、哪些节点脚本自动加、有哪些限制，见 [h3-video 的 queue.md](../../h3-video/references/queue.md) 末节“接入你自己的工作流”。

## 启动脚本（示意）

```bat
set PYTHONPATH=<overlay>
set PATH=<python-env>;<python-env>\Library\bin;%PATH%
<python-env>\python.exe <comfyui-new>\main.py --port <端口> --models-directory <模型库>
```

从桌面快捷方式或本机终端启动，不要靠 SSH 会话保活，会话一断进程就被杀，见 [remote-access.md](remote-access.md)。

## 冒烟测试：只确认能跑

装完先出一段最小的片子，确认整条链是通的，**不要用它判断画质**（低分辨率短片不能代表成片画质，见 h3-video 的 quality-eval.md）：

1. 960×544、90 帧（`17k+5`），任选一个工作流。
2. ComfyUI 日志没有报错；用 `ffprobe` 看成片有视频轨和音频轨、宽高对、帧率 24。
3. 抽几帧看画面不是花屏或纯色。

参考耗时（旧的首帧生视频工作流，挂 Turbo LoRA，同首帧同提示词，单次实测）：4 步约 60 秒，10 步约 120 秒。这不是本配方，只说明机器没有慢到离谱。随后按 h3-video 的 recipes.md 出一段 10 秒的文戏，对比耗时。

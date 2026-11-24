# 模型下载表

什么时候读：第一次装环境要下载模型时，或者工作流报"找不到模型文件"时。

下面是作者出片实际用到的全部模型文件。魔搭（ModelScope）的地址都在 2026-11-25 逐个查过：仓库存在，里面有表里写的那个文件，大小是接口返回的数字。魔搭在国内一般可以直连，下载方法和怎样确认没走代理见 [china-network.md](china-network.md)。

本仓库不存放任何模型文件，只给地址。**除官方仓库外，魔搭上的这些都是第三方用户上传的镜像，不是原作者本人发布的**；能找到原作者发布页时优先去原处下载，并遵守各自的许可。

## 必需的（文戏、武戏都要）

| 角色 | 文件名 | 大小 | 放到 | 魔搭地址 |
|---|---|---:|---|---|
| 主模型 | `Cobijada_H3_Hybrid_int8_convrot_pruned.safetensors` | 21.0 GB | `diffusion_models/` | [alex191/Cobijada_H3_Hybrid_int8_convrot_pruned.safetensors](https://www.modelscope.cn/models/alex191/Cobijada_H3_Hybrid_int8_convrot_pruned.safetensors) |
| 文本编码器 | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 27.1 GB | `text_encoders/` | [Comfy-Org/MiniMax-H3](https://www.modelscope.cn/models/Comfy-Org/MiniMax-H3) 的 `text_encoders/` |
| 视频 VAE | `minimax_h3_video_vae_fp16.safetensors` | 5.2 GB | `vae/` | [Comfy-Org/MiniMax-H3](https://www.modelscope.cn/models/Comfy-Org/MiniMax-H3) 的 `vae/` |
| 音频 VAE | `minimax_h3_audio_vae_fp32.safetensors` | 0.6 GB | `vae/` | [Comfy-Org/MiniMax-H3](https://www.modelscope.cn/models/Comfy-Org/MiniMax-H3) 的 `vae/` |
| 潜空间放大模型（二采用） | `minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors` | 0.7 GB | `latent_upscale_models/` | [LBH-123-AI/Minimax_h3_latent_Upscaler](https://www.modelscope.cn/models/LBH-123-AI/Minimax_h3_latent_Upscaler) 的 `minimax_h3_latent_upscaler_3d_conv_v1/` |

合计约 55 GB。

**主模型的文件名要注意**：作者本机的文件叫 `Cobijada_H3_Hybrid_Uncensored_pruned_hybrid_int8_convrot_pruned.safetensors`，仓库里的工作流和 `config.example.yaml` 写的也是这个名字；魔搭上这份叫 `Cobijada_H3_Hybrid_int8_convrot_pruned.safetensors`。两者大小相同（都是 19.5 GiB），但作者没有比对过哈希，不能保证是同一个文件。下载后要么把文件改成工作流里的名字，要么把工作流和 `config.yaml` 里的名字改成你下载到的。这个模型的原作者是 Winnougan，它是带"去限制"标注的混合版，是否使用请自行判断，见 [uncensor.md](../../h3-video/references/uncensor.md)。

Comfy-Org/MiniMax-H3 是 ComfyUI 官方整理的仓库，Hugging Face 上同名：`huggingface.co/Comfy-Org/MiniMax-H3`，目录结构相同。

## 武戏 LoRA 链（只有打戏需要）

都放到 `loras/`。按下表的顺序串联，强度是作者用的值。

| 顺序 | 文件名 | 强度 | 大小 | 魔搭地址 |
|---:|---|---:|---:|---|
| 1 | `minimax_h3_dmad_full_dareties_v4_step600_comfy_fro.safetensors` | 0.8 | 0.96 GB | [alex191/minimax_h3_dmad_full_dareties_v4_step600_comfy_fro.safetensors](https://www.modelscope.cn/models/alex191/minimax_h3_dmad_full_dareties_v4_step600_comfy_fro.safetensors) |
| 2 | `MysticXXX_MMH3-V1.safetensors` | 0.35 | 0.60 GB | [alex191/MysticXXX_MMH3-V1.safetensors](https://www.modelscope.cn/models/alex191/MysticXXX_MMH3-V1.safetensors) |
| 3 | `motion_speed_slider_mmh3_v1.1.safetensors` | 3.0 | 不到 0.01 GB | [binbin2027/motion_speed_slider_mmh3_v1](https://www.modelscope.cn/models/binbin2027/motion_speed_slider_mmh3_v1) |
| 4 | `H3_Combat_V2.safetensors` | 0.65 | 0.16 GB | [yueyee/H3_Combat_V2](https://www.modelscope.cn/models/yueyee/H3_Combat_V2) |
| 5 | `Motion_Repair_V2.safetensors` | 0.35 | 0.16 GB | [binbin2027/Motion_Repair_V2](https://www.modelscope.cn/models/binbin2027/Motion_Repair_V2) |

合计约 1.9 GB。每个 LoRA 是做什么的、第 2 个的来历披露，见 [lora.md](../../h3-video/references/lora.md)。

## 下载示例

魔搭的单文件地址格式是 `https://www.modelscope.cn/models/<所有者>/<仓库>/resolve/master/<文件路径>`，例：

```bash
curl -L -C - -o minimax_h3_audio_vae_fp32.safetensors \
  "https://www.modelscope.cn/models/Comfy-Org/MiniMax-H3/resolve/master/vae/minimax_h3_audio_vae_fp32.safetensors"
```

`-C -` 是断点续传。文件清单和每个文件的 SHA-256 可以从这个接口拿到，下完建议校验：

```bash
curl -s "https://www.modelscope.cn/api/v1/models/Comfy-Org/MiniMax-H3/repo/files?Recursive=true"
```

## 没有列进来的

- 出参考图用的图像模型：作者走的是在线图像接口，不在本机。
- 可选的本地文本大模型：见 [llm-basalt.md](llm-basalt.md)。
- 试过后不用的模型（超分、其他底模、加速 LoRA）：见 [tried-and-dropped.md](../../h3-video/references/tried-and-dropped.md)。

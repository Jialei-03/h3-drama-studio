# scripts

全部脚本读 `config.yaml`（字段样例在仓库根的 `config.example.yaml`）和命令行参数，不写死路径、主机、模型文件名、镜头名、时间点。共用的小模块是 `_config.py`（找 `--config`、`$H3_CONFIG`、当前目录、仓库根的 `config.yaml`）。每个脚本的 `--help` 里有用途、输入、输出和用法示例。

**验证状态（请先读）：出图与出片侧的脚本（`relay_img.py` 到 `asr.py`）没有在干净环境端到端验证。** 它们没有对真实的出图服务和真实的 ComfyUI 跑过。队列脚本有一项更强的验证：它 dry-run 生成的工作流和作者主机实际提交的工作流逐节点一致。本机能做的验证是：`py_compile` 通过（Python 3.9、3.12、3.13）、`--help` 可用、`--dry-run` 走通数据流，以及用 localhost 上自己写的模拟接口跑通请求格式、队列循环、续跑和拒绝处理。具体见下面"验证了什么"。

## 全部脚本

| 脚本 | 做什么 | 最简用法 |
|---|---|---|
| `relay_img.py` | 用兼容 OpenAI 图像接口的服务出一张图（带参考图走 edits，不带走 generations）；地址和密钥只从环境变量读 | `relay_img.py out.png prompt.txt ref1.png ref2.png` |
| `kf_batch.py` | 按一份 yaml 清单并发批量出图（定妆图、场景图、受损阶段场景图……） | `kf_batch.py keyframes.yaml --tag r1 --workers 4` |
| `build_shots.py` | 分段提示词数据（yaml）→ 队列用的 `shots.json` + 逐句中文翻译 `prompts_zh.md`；文戏预设不挂 LoRA，武戏预设挂 `models.fight_loras` | `build_shots.py segments.yaml --out shots.json` |
| `make_full_script.py` | 从同一份数据生成给人看的中文全剧本（结构表、状态表、每段画面台词声音和生成方法） | `make_full_script.py segments.yaml --out full_script.md` |
| `check_script.py` | 出片前机械检查（通用检查 + 一份规则 yaml 里的项目专属规则） | `check_script.py shots.json --rules rules.yaml --data segments.yaml` |
| `drama_queue.py` | 出片队列；读你自己导出的 ComfyUI 工作流和 `workflow:` 映射表；子命令 `run` / `check-map` / `submit` | `drama_queue.py check-map`，再 `drama_queue.py run --dry-run --shots shots.json`，最后 `drama_queue.py run` |
| `review_ep.py` | 验片：硬切数、听写台词对剧本、可选八帧联系表 | `review_ep.py --shots shots.json --videos renders/ --take 530 --sheet` |
| `asr.py` | 听写台词，并按剧本台词定出每句实际说话的起止秒（单段，验片用；mlx-whisper 或 openai-whisper，可选） | `asr.py clip.mp4 --lines lines.txt` |
| `chain_join.py` | 武戏逐段接续的后处理：剪掉上下文帧、颜色匹配、出接缝预览 | `chain_join.py prev.mp4 new.mp4 --out-dir work/` |
| `splice.py` | 按片段清单（yaml：文件、可选的裁剪起止帧、分组）规范化每段并拼接 | `splice.py clips.yaml -o build/full.mp4 --fix-audio` |
| `fix_audio.py` | 拼接后重建音轨，让音频时长严格等于画面时长 | `fix_audio.py full.list.txt full_raw.mp4 full.mp4` |
| `impact_frames.py` | 在真正的大招上叠几帧冲击画面（九宫格 + 位置表 yaml；`--find-peak` 帮你找峰值帧） | `impact_frames.py impacts.yaml film.mp4 out.mp4 --dry-run` |
| `retime_subs.py`、`render_subs.py` | 对整片逐词识别、给每句台词出起止时间建议（或只做剪片平移）；渲染电影感对白字幕（需要 `fonts.zh`） | `retime_subs.py script.tsv film.mp4 -o cards.tsv`；`render_subs.py cards.tsv film.mp4 out.mp4` |
| `mix_bgm.py` | 给成片混背景音乐（对齐、淡入、校平、推高、混响尾巴、原声增益、限幅全在一份 yaml 里；不带音乐） | `mix_bgm.py bgm.yaml film.mp4 out.mp4 --song 有授权的歌.flac` |
| `render_lyrics.py` | 歌词字幕（歌词文件由你提供，仓库不含任何歌词，脚本不打印歌词；需要 `fonts.zh`、`fonts.en_italic`） | `render_lyrics.py lyrics.txt times.tsv film.mp4 out.mp4 --bgm-plan bgm.yaml` |
| `embed_cover.sh` | 把封面作为附图嵌进 mp4，不重新编码 | `embed_cover.sh final.mp4 cover.jpg out.mp4` |

## 出图与出片侧怎么串起来

```
keyframes.yaml ──kf_batch.py──▶ 定妆图 / 场景图（relay_img.py 出单张）
segments.yaml ──build_shots.py──▶ shots.json + prompts_zh.md ──check_script.py（rules.yaml）
              └─make_full_script.py──▶ full_script.md（给人看）
shots.json ──drama_queue.py run（config.yaml 的 workflow: + 你导出的 API json）──▶ 成片 + results.json
成片 ──review_ep.py（内部用 asr.py）──▶ review_<take>.md
```

带注释的示例数据在 `examples/gemini-revenge/data/`：`segments.example.yaml`（一段文戏、一段武戏）、`rules.example.yaml`、`keyframes.example.yaml`；后期侧有 `clips.example.yaml`（拼接清单）、`subs.example.tsv`（字幕卡）、`impacts.example.yaml`（冲击帧位置）、`bgm.example.yaml`（配乐参数）、`lyrics_times.example.tsv`（歌词时间表，占位数字）。。

关键约定：

- **出图地址和密钥**只从环境变量读，变量名在 `image_api.base_url_env` / `key_env`；`--dry-run` 只打印将发送的内容，不读密钥的值。
- **工作流不随仓库分发。** `drama_queue.py` 按 `workflow.nodes` 映射表改写你自己导出的工作流，哪些节点要你已经有、哪些由脚本自动加、有哪些限制，见 [skills/h3-video/references/queue.md](../skills/h3-video/references/queue.md) 末节"接入你自己的工作流"。
- **take 号**：改了提示词就换 take（`build_shots.py --take N`），队列用 `<id>_t<take>` 判断一段是否出过。
- `check_script.py` 退出码：有错误为 1，只有警告为 0（加 `--strict` 则警告也算失败）。

## 验证了什么（出图与出片侧）

| 脚本 | 本机验证 | 没验证的 |
|---|---|---|
| `relay_img.py`、`kf_batch.py` | `--dry-run` 打印提示词和请求格式；对 localhost 上的模拟接口跑通 generations（JSON）和 edits（multipart，`image[]` 多张）、Bearer 密钥头、b64 返回、失败重试和报错退出码 | 真实服务（不同服务对 `size`、`n`、`image[]` 的支持可能不同） |
| `build_shots.py`、`make_full_script.py` | 用示例数据（文戏、武戏，另造了带 `first`、`last`、`ctx` 的 4 段测试数据）组装 shots.json 和中英文提示词，占位符解析、take 重映射、预设 | 其他故事的数据；shots.json 没有真的出片 |
| `check_script.py` | 示例数据零问题；另造了十几处故意写错的用例（超时长、残留占位符、缺时间码、打戏台词、禁用词、错误锚点、`not_before` 等），逐项报出 | 规则覆盖面取决于你写的规则 |
| `drama_queue.py` | 用仓库自带的 `workflows/h3_base.api.json` 做 dry-run，生成的工作流与作者主机实际提交的两份（文戏、带接续的武戏）逐节点一致。另用手写的测试工作流：`check-map`（含故意填错的映射）、`run --dry-run`（含 up2、LoRA 链、首尾帧、`ctx`、`save_stage1` 的节点改写和连线完整性）、`submit` 合并；用 localhost 模拟的 ComfyUI 接口跑通真实队列循环：提交、轮询、写 `results.json`、联系表、`ctx` 的 ffmpeg 截取 22 帧、首帧取清晰帧、被拒绝的工作流计 2 次后跳过、`STOP` 退出 | 真实 ComfyUI 的类型校验和出片；`--upload` 的 scp（只打印了命令） |
| `review_ep.py`、`asr.py` | 一段真实的带台词成片：切点检测、mlx-whisper 听写、对剧本的 ✓ 判定、联系表；缓存命中 | openai-whisper 后端；批量多段和接续段的路径只用示例数据走过 |

## 后期侧怎么串起来

```
clips.yaml ──splice.py（--fix-audio）──▶ 全片（音轨已重建；接续段先 chain_join.py）
          ──impact_frames.py（impacts.yaml）──▶ 冲击帧版
          ──retime_subs.py → render_subs.py（cards.tsv）──▶ 字幕版
          ──embed_cover.sh──▶ 带封面
          ──mix_bgm.py（bgm.yaml、你有授权的歌）──▶ 配乐版
          ──render_lyrics.py（你提供的歌词文件、times.tsv）──▶ 歌词版
```

顺序不能换，原因见 [skills/drama-postproduction/SKILL.md](../skills/drama-postproduction/SKILL.md)。字体不随仓库分发：`render_subs.py` 和 `render_lyrics.py` 读 `config.yaml` 的 `fonts.*`（见 `config.example.yaml`），没配置就报错并提示，没有系统字体路径默认值。

## 验证了什么（后期侧）

2026-11-24 在 macOS、Python 3.12、ffmpeg 8.0 上，用作者《Gemini的复仇！》的真实片段和成片截取（只读，产物放在 `/tmp`）逐个跑过；`py_compile` 全部通过，每个脚本 `--help` 可用。

| 脚本 | 实际跑了什么 | 结果 | 没验证的 |
|---|---|---|---|
| `chain_join.py` | 一对真实的接续片段（260 帧，开头 22 帧是上下文） | 输出 238 帧，第 0 帧 = 原片第 22 帧（不调色时 PSNR 44 dB）；调色后增益约 0.95–0.97；出了 3 秒接缝预览；音画等长 | 其他 `--n`、白光接缝跳过调色的分支只在代码里 |
| `splice.py` + `fix_audio.py` | 4 段（含一段 30 fps 1280×720 无音轨的合成片、一段 `start_frame`/`end_frame` 裁剪）；12 段真实接续片段；`--group`；缓存命中 | 裁剪帧精确；12 段拼完解码实测音频比画面长 0.387 s，重建后 +0.003 s；无音轨段补静音 | 24 段全片规模；非整数帧率 |
| `embed_cover.sh` | 真实封面 jpg、合成 png 封面、对已带封面的成片重嵌 | 画面和音轨码流 md5 与输入一致；封面为 mjpeg + `attached_pic` | 其他封装格式（只做了 mp4） |
| `render_subs.py` | 5 张卡（含英文、`……`）：预览和整段渲染；示例字幕卡文件 | 样式与原版一致（看了截图），音轨 md5 不变 | 其他字体、其他分辨率的等比缩放 |
| `retime_subs.py` | 全片 40 句，真实 mlx-whisper（离线用本机已有模型）；`--shift` 平移；yaml 输出 | 31 句 OK、9 句标"低匹配/没对上"；对白密集段起点比作者耳朵定的晚 0.1–0.5 s，个别 0.8 s（建议值，需人听） | openai-whisper 后端；繁体输出 |
| `impact_frames.py` | 纯色九宫格 + 一段 192 帧真实成片，2 处冲击（含负片）；`--dry-run`、`--find-peak`、`shifts`、撞帧和越界检查 | 被改的帧正好是表里列的 18 帧，间隔帧和负片中间的原画面不变，帧数不变，音轨 md5 不变 | 整片规模（约 5400 帧）的渲染耗时 |
| `mix_bgm.py` | ffmpeg 合成的测试音（不是真音乐）+ 60 秒真实成片；点击音对齐、校平、推高、混响尾巴、`shifts`、喊招增益、限幅、带封面的成片 | 对齐误差约 0.1 ms；校平把轻 12 dB 的一段补到只低约 4 dB；画面码流 md5 不变；成片响度和真峰值自动量出 | 真实歌曲的听感；`target_lufs`；两首歌接力 |
| `render_lyrics.py` | 自己编的 3 对无意义占位文本；`--offset`/`--range`、`--bgm-plan`、`--preview`、带封面的成片 | 时间公式与文档一致；封面流和音轨保留；终端没有歌词文字 | 56 对真实规模；`--zh-first` |

## 依赖

Python 3.9 以上；ffmpeg 和 ffprobe；numpy、Pillow、PyYAML；`asr.py` / `review_ep.py` 的听写要 mlx-whisper（Apple 芯片）或 openai-whisper 二选一（可选，没装会给出清楚的报错，`review_ep.py --no-asr` 可跳过）。`scp` 只在 `drama_queue.py submit --upload` 用到。

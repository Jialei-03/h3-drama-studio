# 批量队列：排队、中断、续跑、通宵、早上检查

什么时候读：要把一批镜头排进队列、要暂停或恢复、要换队列脚本、要通宵出片，或者早上要检查出了什么。

队列脚本是 `scripts/drama_queue.py`，运行在出片主机上，用 ComfyUI 的 HTTP 接口提交任务。下面的字段和行为来自作者的原版脚本；仓库里的版本把路径改成了读 `config.yaml`（`host.queue_dir`、`host.comfyui_url`、`host.comfyui_output`、`host.comfyui_input`），并且**不再带工作流文件、不再写死节点编号**：你把自己导出的工作流和一张映射表填进 `config.yaml`，脚本按表改写节点，见本文末尾"接入你自己的工作流"。如有出入以脚本为准。

状态：重写后的脚本用仓库自带的 `workflows/h3_base.api.json` 做 dry-run，生成的工作流和作者主机当时实际提交的两份（一段文戏、一段带接续的武戏）逐节点一致，结构和参数都相同；队列循环、续跑、接续截帧、拒绝处理用模拟的 ComfyUI 接口跑通过。**这个重写版脚本本身还没有向真实的 ComfyUI 提交过任务。**原版（节点编号写死的那份）出过作者的全部 281 段。

子命令：`drama_queue.py run`（跑队列；`--dry-run` 只生成并打印将提交的工作流 json，不联网）、`check-map`（检查映射表）、`submit`（把一轮新 shots 合并进总清单，可 `--upload`）。

## 它怎么工作

- 每一轮重新读 `shots.json`，按文件里的顺序取第一条"没出过、且依赖已满足"的 shot 提交，等它出完，写 `results.json`。没有活干就睡 60 秒再看。
- 因为每轮重读，**队列运行中可以随时改 `shots.json`**（追加、重排、删除未开始的），正在渲的那段不受影响。
- 唯一键是 `<id>_t<take>`。**改了提示词要换 take 号**，否则队列认为这条已经出过、不会重渲。
- 失败自动重试：同一条最多试 2 次（`tries` < 2），第二次还失败就跳过，不再碰。映射错误、ComfyUI 校验不通过（提交时被拒）也各计一次失败，原因写进 `results.json` 的 `messages`，不会无限重试同一张废图。
- 依赖：`first`、`last`、`ctx` 引用了别的 shot（`@id_tN`）时，被引用的那条必须 `success`，否则这条一直排不上。
- 每段出完后对 ComfyUI 调 `/free` 卸载模型再睡 10 秒，让下一段从干净的显存开始。所以每段的耗时都含模型重新加载。
- 请求本机 ComfyUI 时脚本显式关闭了代理：回环地址不该走代理软件。
- 目录里出现 `STOP` 文件：队列在**当前这段结束后**退出。它只在两段之间检查，不会打断正在渲的那段。

## shots.json 字段

必填：`id`、`seconds`、`seed`、`prompt`、`images`。其余都是可选；**没写的字段沿用你导出的工作流里已有的值**（原版脚本是落到早期的 15 步单采，仓库版不再这样）。`build_shots.py` 会把完整配方写进每条 shot，另外写入的 `kind`、`refs` 队列不读，只给 `check_script.py` 和 `review_ep.py` 用。

| 字段 | 默认 | 含义 |
|---|---|---|
| `id` | | 段名，和 `take` 组成键 `<id>_t<take>` |
| `take` | 1 | 版本号，同一段每重出一次换一个号 |
| `seconds` | | 想要的成片秒数。脚本换算成帧数并向上取到 `17k+5`；带 `ctx` 时先加 22 帧 |
| `seed` | | 种子 |
| `prompt` | | 提示词 |
| `images` | | 参考图文件名列表，文件须已在 ComfyUI 的 input 目录里，最多 9 张 |
| `w`、`h` | 工作流里的值 | 一采宽高（现用配方写 1024、576） |
| `unet`、`clip` | `models.unet`、`models.text_encoder`，再没有就用工作流里的 | 模型文件名 |
| `loras` | 无 | `[[文件名, 强度], ...]`，按顺序串联 |
| `shift` | 无 | `[视频, 音频]`，接 `MiniMaxH3SigmaShift`，现用 `[12, 3]` |
| `sampler` | 工作流里的值 | 一采采样器，现用 `euler` |
| `sigmas` | 工作流里的值 | 手写 sigma 字符串，现用 RunningHub 10 步曲线 |
| `sched` | 无 | `["beta", 33]`：用调度器代替手写 sigma |
| `ref_size` | 工作流里的值 | 参考图尺寸策略，现用 `match` |
| `dense` | false | true 则关掉稀疏注意力 |
| `first`、`last` | 无 | 首帧、末帧锚点：input 里的图片名，或 `"@id_tN"` |
| `ctx` | 无 | `"@id_tN"`：把那段末尾 22 帧加音频锚在第 0 帧，用于武戏接续 |
| `ctx_frames`、`ctx_audio` | 22、true | 接续帧数；是否连音频一起接 |
| `up2` | 无 | 专属二采：`{"w","h","sched","split","sampler"}`，宽高须为 32 的倍数，见 [recipes.md](recipes.md) |
| `save_stage1` | false | 同时把一采结果存成 `<id>_t<take>_stage1` 视频（要有 `up2`） |

原版还有旧版二采 `up` 和超分任务 `kind: sr/sr2`（SeedVR2）；两者已弃用（见 [tried-and-dropped.md](tried-and-dropped.md)），仓库版不再支持。

几个细节：

- `first: "@id_tN"` 取那段末尾 0.5 秒里最清晰的一帧，不是最后一帧。最后一帧常带运动模糊，模糊会带进下一段的开头（作者片中一次相邻两段的接缝翻车）。`:end`、`:start` 可强制取末帧或首帧。
- `ctx` 的接续帧和音频要用 ffmpeg 从上一段截出来，主机上要有可用的 ffmpeg。拼接时用 `scripts/chain_join.py` 把这 22 帧剪掉并做颜色匹配。
- **配方字段仍然要写进每条 shot。** 没写的字段沿用工作流里已有的值，那不一定是现在的配方。作者用一个预设字典合并进每条 shot，仓库里是 `build_shots.py` 的文戏/武戏预设。

## 记录文件

- `results.json`：键是 `<id>_t<take>`，值如 `{"status": "success", "seconds_wall": 906, "frames": 243, "tries": 1, "finished": "03:41", "video": "…mp4"}`。失败时 `status` 是 `error`，多一个 `messages`（最后两条错误信息）。`seconds_wall` 是墙钟秒数，含模型加载。
- `<id>_t<take>.sheet.jpg`：每段出完生成一张 4×2 的八帧联系表，每格标时间，用来先扫一眼。
- `queue.log`：`BEGIN <key>`、`END <key> <status> <秒>`、`ERROR`、`queue start`、`queue stop`。

## 中断当前任务、暂停

要把显卡让给别的事时，**先建 STOP，再中断**。顺序反了，当前这段被中断后队列会马上提交下一段。

```powershell
$R = "<host.queue_dir>"; $u = "<host.comfyui_url>"
New-Item -ItemType File -Force "$R\STOP" | Out-Null                       # 1. 不再取新的
Invoke-RestMethod -Method Post -Uri "$u/queue" -ContentType application/json -Body '{"clear":true}' | Out-Null   # 2. 清掉排队的
Invoke-RestMethod -Method Post -Uri "$u/interrupt" | Out-Null             # 3. 中断正在渲的
Start-Sleep 25
Invoke-RestMethod -Method Post -Uri "$u/free" -ContentType application/json -Body '{"unload_models":true,"free_memory":true}' | Out-Null
(Invoke-RestMethod "$u/queue").queue_running.Count                        # 4. 应为 0；再用 nvidia-smi 看显存降下来没有
```

被中断的那段在 `results.json` 里是 `error`、`tries` 加 1。**恢复后它会被自动重试一次**（按代码读出，没有专门测过）；如果已经 `tries` 为 2，要删掉那条记录或换 take 号。

### 暂停时写一份恢复清单

写清三样：已出好并留用的段（段名、用哪一版）、待重做或待跑的段（及原因）、恢复时按什么顺序做（传参考图、改 `shots.json`、删 STOP、重启队列、渲染顺序）。暂停几小时后你自己也会忘。

## 续跑

1. 确认 `shots.json` 和 `results.json` 状态符合预期。
2. 删掉 `STOP`。
3. 用能脱离 SSH 会话的方式启动队列：

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = "cmd /c <python> -u <repo>\scripts\drama_queue.py run > <host.queue_dir>\queue.out 2>&1" }
```

直接在 SSH 会话里启动，会话一断进程就被杀（见 [local-ai-workstation 的 remote-access](../../local-ai-workstation/references/remote-access.md)）。

## 换队列脚本的安全做法

不要在队列运行时直接杀进程换脚本：ComfyUI 里的任务还在跑，`results.json` 却没有记录，重启后同一段会被再提交一次，白占 20 多分钟显卡（按代码读出）。做法：

```powershell
$R = "<host.queue_dir>"
New-Item -ItemType File -Force "$R\STOP" | Out-Null
while (-not ((Get-Content "$R\queue.log" -Tail 1 -Encoding UTF8) -match "queue stop")) { Start-Sleep 15 }   # 等当前这段出完
Copy-Item -Force "<新版>\drama_queue.py" "<repo>\scripts\drama_queue.py"
Remove-Item -Force "$R\STOP"
# 然后用上面的 Win32_Process 方式重新启动
```

等待可能长达一整段的时间（文戏约 15–20 分钟，武戏约 24–27 分钟）。赶时间就走"暂停"流程中断当前段，代价是这一段从头来。

## 通宵运行

**睡前：**
1. 每种新写法先出一段再排整夜：二采、`first`、`ctx` 各试一次。作者第一段接首帧的片，就在二采里因锚点尺寸失败，修好后重跑才成功。
2. 被依赖的段排在前面；`@` 引用的键必须真的存在。上游失败两次，下游会永远排不上，队列空转。
3. 参考图都已在 ComfyUI 的 input 目录；磁盘剩余空间够；文本模型已卸载，`nvidia-smi` 显示显存基本空。
4. 算好预计完成时间：总片长（秒）× 1.5–2 分钟（文戏）或 × 2.4–2.7 分钟（武戏）。
5. 主机别休眠、别自动重启更新（常识性防护，作者没有专门验证）。
6. 启动后确认 `queue.log` 出现 `BEGIN`，ComfyUI 的 `/queue` 里有一个在跑。

**夜里：** 不要碰主机。测速和出片都对同机负载敏感，别通过 SSH 拷大文件。

## 早上检查清单

逐项勾选的版本在 `templates/morning-checklist.md`。顺序是：

1. **队列还活着吗**：`queue.log` 末尾是 `END`、`BEGIN` 还是 `queue stop`；搜 `ERROR`。`shots.json` 里还有没出的、log 却没有新的 `BEGIN`，多半是依赖的上游没成功。
2. **`results.json` 里有没有非 `success`**，读 `messages`。用 ffprobe 核对成片宽高（1536×864）、帧率（24）、时长约等于 `frames/24`、有音频轨。
3. **先看联系表**（每段八帧）：扫整段白屏或灰屏、人物变形、场景变样。
4. **自动检查**：`scripts/review_ep.py --shots shots.json --videos <成片目录> --take N --sheet` 数每段的硬切数并听写台词对剧本（用法和已知误报见 [qc.md](../../drama-scenes/references/qc.md)）。**只用来排出"先看哪几段"，以眼睛和耳朵为准。**
5. **逐段看原片**：动作演完没有、结尾姿势和机位、台词是否清楚；有 `ctx` 的段，用 `chain_join.py` 生成的接缝视频看前后接不接得上。
6. **决定**：留用、换种子重渲，还是改提示词重写（换 take 号），记进清单。

## 出完片释放显存

队列每段结束都会 `/free`，所以夜里跑完之后显存通常已经空了。仍然要在换用显卡之前确认：`nvidia-smi` 看已用显存；还高就再发一次 `/free`；仍不降就关掉 ComfyUI 进程。ComfyUI 不会自己释放显存，加载过的模型会一直占着约 13 GiB，接着启动文本模型会因显存不足缩小缓存。

## 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| `error`，信息里有 `shape` | 二采宽高不是 32 的倍数，或锚点没在放大后的潜空间重加 | 见 recipes.md |
| 改了提示词没有重渲 | take 号没变 | 换 take 号 |
| 同一段被渲了两次 | 队列进程被杀后重启，ComfyUI 里旧任务还在 | 用 STOP 流程停 |
| 队列在，但什么都不出 | 引用的上游没成功 | 补跑上游，或去掉引用 |
| `sheet_error` | 多半是主机上 ffmpeg 不可用 | 成片本身没问题，装好 ffmpeg 即可 |
| 出片速度突然翻倍变慢 | 二采分辨率太大溢出共享显存；主机上有别的负载；torch 的 CUDA 版本不对 | 见 tried-and-dropped.md 和 local-ai-workstation 的 pitfalls.md；查 `nvidia-smi` |
| `映射错误：节点 N 没有输入 'xxx'` | `workflow.nodes` 里的节点编号或输入名和你导出的 json 对不上 | 跑 `check-map`，按提示改 |
| `results.json` 里 `ComfyUI 拒绝了工作流` | ComfyUI 的类型校验没过：模型文件名不在它的列表里、节点输入名和你的 ComfyUI 版本不同…… | 读 `messages` 里的原文；对照 dry-run 存下的 json 在 ComfyUI 里加载看 |

## 接入你自己的工作流

什么时候读：第一次配 `workflow:` 映射表，或者换了工作流、`check-map` 报错的时候。

原版脚本依赖一份第三方的工作流导出文件，并在代码里写死了节点编号（例：模型加载器、采样器、解码、保存各是哪个编号）。那份文件不能随仓库分发，仓库版改成：**你用自己的 H3 工作流，脚本按映射表改写它的节点**。

### 步骤

1. 在 ComfyUI 里打开你自己的 H3 参考生视频工作流（先确认它在界面里能出一段片），用菜单"导出 (API)"保存 json。不是普通保存：普通保存的 json 有 `nodes` 列表，脚本会拒绝。
2. 把路径填到 `workflow.api_json`，把下表的角色逐个对应到 json 里的节点编号（json 的顶层键就是编号；`class_type` 能帮你认节点）。`config.example.yaml` 里填好的编号对应仓库自带的 `workflows/h3_base.api.json`，用它就不用改。
3. `python3 scripts/drama_queue.py check-map`：核对节点在不在、类型对不对、关键连线是否符合脚本的假设，并列出哪些功能因为缺角色而不可用。
4. `python3 scripts/drama_queue.py run --dry-run --shots shots.json --only <id> --save-dir 某目录`：不联网，把一条 shot 写进你的工作流，打印新增和被改写的节点、检查连线完整性（连线都指向存在的节点、无环），并存下完整 json。可以把存下的 json 拖进 ComfyUI 界面看一眼。
5. 真提交前，每种新写法各出一段最短的：纯文戏、二采、首帧、接续（原因同"通宵运行"第 1 条）。

### 映射表：脚本对每个角色做什么

`workflow.nodes.<角色>` 写 `{node: 编号, input: 输入名}`；`input` 不写用默认名。`cond`、`guider`、`pass1`、两个 VAE 只需要 `node`。

| 角色（默认输入名） | 通常的节点 | 脚本做什么 |
|---|---|---|
| `unet`（`unet_name`）、`clip`（`clip_name`） | UNETLoader、CLIPLoader | 写入模型文件名（shot 里有就用，其次 `models.*`，都没有就不动） |
| `prompt`、`width`、`height`、`length`、`ref_size` | MiniMaxH3ReferenceToVideo | 写入提示词、一采宽高、帧数、参考图尺寸策略。宽高若来自别的原始值节点，就把角色指到那个节点和它的输入名 |
| `ref_images`（前缀 `ref_images.ref_image_`） | 同上 | 先删掉该节点上这一组已有的输入，再按 shot 的 `images` 逐张新建 LoadImage 接上 |
| `seed`（`noise_seed`） | RandomNoise | 写种子；二采复用同一个节点 |
| `sampler`（`sampler_name`）、`sigmas`（`sigmas`） | KSamplerSelect、ManualSigmas | 写一采采样器和 sigma 字符串；shot 写了 `sched` 时，整个 sigma 节点原地换成 BasicScheduler |
| `model_in`（`model`） | 你工作流里紧跟模型加载器的那个节点 | 把它的 `model` 输入接到链尾：加载器 → LoRA → SigmaShift |
| `cond` | 同参考生视频节点 | 条件输出（0）和空潜空间（1）的来源；锚点节点从这里取 |
| `guider` | BasicGuider | 把 `conditioning` 改成锚点链的末端；`dense` 时把 `model` 直接接到 `model_in` 节点的输出 |
| `pass1` | SamplerCustomAdvanced | 一采采样节点；二采从它的输出 1（去噪后的音画联合潜空间）取数 |
| `video_vae`、`audio_vae` | VAELoader | 锚点节点和一采预览解码引用它们 |
| `decode_video`、`decode_audio`（`samples`） | VAEDecode、VAEDecodeAudio | 二采时把 `samples` 改接到二采输出 |
| `save`（`filename_prefix`） | SaveVideo | 写成 `<host.output_subdir>/<id>_t<take>`；队列靠这个前缀在 ComfyUI 的返回里找成片 |

另有 `workflow.drop_nodes`：要从导出里删掉的节点编号，例如你原工作流里自带的加速 LoRA 加载器（由脚本按 shot 的 `loras` 重建）。被删的节点不能再被别的节点引用，`check-map` 会查。

### 哪些是脚本自动加的，哪些要你的工作流里已经有

| 你的工作流里必须已经有 | 脚本自动加（编号前缀 `q_`） |
|---|---|
| 模型、编码器、两个 VAE 的加载器；参考生视频条件节点；BasicGuider；RandomNoise；KSamplerSelect；一个能写 sigma 字符串的节点；一采 SamplerCustomAdvanced；视频、音频两个解码节点，且 `samples` **直接**接在一采的输出 1 上；CreateVideo → SaveVideo | 参考图的 LoadImage；LoRA 链；`MiniMaxH3SigmaShift`；首尾帧和接续的 LoadImage / LoadVideo / GetVideoComponents / `MiniMaxH3AddGuide`；二采的全部节点；`save_stage1` 的另存分支 |

### 二采 `up2` 是怎么接进图里的

一采那条链（条件 → guider → 一采采样节点）**原样保留，跑完整条 sigma 曲线**。脚本在它后面接：

1. `LTXVSeparateAVLatent`：把一采输出 1 拆成视频潜变量和音频潜变量；
2. `LatentUpscaleModelLoader`（`models.latent_upscaler`）+ `MiniMaxH3LatentUpscaleWithModel`：视频潜变量放大到 `up2.w × up2.h`（要 32 的倍数，脚本会先拦）；
3. `LTXVConcatAVLatent`：放大后的视频潜变量和**原样的**音频潜变量拼回去；
4. `BasicScheduler`（`up2.sched`，模型取链尾，也就是带 SigmaShift 的）→ `SplitSigmas`（在 `up2.split` 处切开）→ 取后半段；
5. 第二个 `SamplerCustomAdvanced`：噪声用 `seed` 节点（与一采同一个种子），采样器 `up2.sampler`，sigmas 取后半段，在放大后的潜空间上重新加噪后采样；
6. 把 `decode_video`、`decode_audio` 的 `samples` 改接到第二个采样节点的输出 1。

有首帧、末帧或接续锚点时，条件是按一采潜空间的尺寸写进去的，放大后会 `shape mismatch`。所以脚本把每个 `MiniMaxH3AddGuide` 复制一份，`latent` 改接放大后的潜变量，另建一个 `guider2`（复制你的 guider，条件换成新的链）给二采用。

### 接续 `ctx` 是怎么接进图里的

`ctx: "@id_tN"`：队列从 `results.json` 取那一段的成片，用 ffmpeg 截**最后 22 帧和对应的音频**，放进 `host.comfyui_input`；图里加 `LoadVideo` → `GetVideoComponents`，再用一个 `MiniMaxH3AddGuide`（`frame_idx` 为 0，同时给图像和音频、带 `audio_vae`）串在条件上。帧数 = 新内容秒数 × 24 + 22，再向上取到 17k+5。拼接时的剪掉和调色见 `scripts/chain_join.py`。首帧 `first: "@id_tN"` 同理，只是取上一段末尾 0.5 秒里最清晰的一帧；`first` 和 `ctx` 都锚在第 0 帧，不能同时写。

### 限制（如实写明，不假装通用）

- **只适配"一条参考生视频链 + 一个 SamplerCustomAdvanced"的拓扑**，也就是原版那种。如果你的工作流在采样和解码之间还有别的节点（拆分、后处理），二采接不上，要自己改映射或扩展脚本。
- 脚本自己加的节点，类名和输入名是按作者用的 ComfyUI 0.45 写死的。你的版本里输入名不同，dry-run 看不出来，只有提交时才会被 ComfyUI 拒绝（原文记在 `results.json`）。本地只检查连线存在和无环，**不做类型校验**。
- `save_stage1` 克隆你的解码、CreateVideo、保存三个节点，要求 `save` 的 `video` 直接接 CreateVideo。
- 二采的 BasicScheduler 取链尾（`model_in` 之前）的模型，不经过 `model_in` 之后的补丁（稀疏注意力之类）；这和原版一致。
- 导出的 json 里不应还留着 `SetNode`/`GetNode` 之类的虚拟节点，`check-map` 会提醒；它们在新版前端"导出 (API)"时应被展开，没有在多种工作流上验证（未验证）。


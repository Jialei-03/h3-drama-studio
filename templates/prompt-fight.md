# 武戏提示词模板

用在环节 6（武戏出片）。英文骨架 + 中文注释：**所有以 `#` 开头的行是给你的说明，使用前删掉**；`{花括号}` 换成你的内容。
细则见 `skills/drama-scenes/references/fight.md`，运镜见 `camera.md`，接续见 `continuation.md`，尺度和召唤物见 `summons.md`。配置（武戏 LoRA 链）见 `skills/h3-video/references/recipes.md`、`lora.md`。一段真实写完的武戏提示词见 `examples/gemini-revenge/prompts.md`。

## 开写前先核对

- [ ] **上一段已经渲完并验过片**：抄的是它**实际的**结尾姿势、机位、间距、伤（不是剧本里写的）。武戏一次只渲一段
- [ ] 这一段是武戏：有招式、命中、召唤物。一旦要有长台词就拆成两段
- [ ] 段长 5–10 秒；接续段新内容 ≤ 9.9 秒，含 22 帧接续总帧数 ≤ 260（16 GB 显存的安全线）
- [ ] 只放一两个能演完的动作；写不完就拆段，不要压缩时间码
- [ ] 每个镜头、每一拍都写时间码；写明每个镜头是在几秒硬切，还是不切
- [ ] 第一帧就是全速动作；结尾收在冲击、闪白或被吞没上
- [ ] 速度只用正面描述（不写 `no slow motion`、`never pauses`）
- [ ] 人物间距写具体数字，并写明本段谁都不挪步
- [ ] 打斗中不说话；只有招牌大招在动作中途用英文喊一声
- [ ] 不用关键帧：参考图只给人物、场景（有召唤物再加召唤物图）；每个镜头写起始机位
- [ ] 只有一个人或只有巨兽的段，不套用两人对打的规则

## 模板

```text
# ---------- 1. 主体定义 ----------
subject_definitions:
<Subject 1> is {角色 A 的外观锁定项，含持械手：always in her right hand with a normal forward grip ...}.
<Subject 2> is {角色 B 的外观锁定项}.
# 场景：写受损阶段的说法（来自状态表）；受损场景要换成对应阶段的场景参考图。
<Subject 3> is {场景：布局、地标；当前受损阶段：只有地面小范围损伤，所有柱子都立着}.
# 有召唤物再加一个主体，外形描述一字不差，并写 never changes shape or color。
# <Subject 4> is {召唤物}.

# ---------- 2. 摘要：写接上一段的哪个画面 ----------
summary:
[reference generation] The video continues straight on from the previous shot, {上一段结尾的画面}. {N} hard-cut shots: {镜头 1 做什么}; {镜头 2 做什么}; ...; ends in the middle of motion, on an impact.

# ---------- 3. 主体出现在哪些镜头 ----------
retention_analysis:
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 2> (appears in [Shot 1], [Shot 4]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - the layout, architecture, lighting, and key landmarks are retained.

# ---------- 4. 正文 ----------
detailed_description:
# (a) 风格段：全片逐字相同，每段复制（与文戏相同的一份）。
The target video is a photorealistic live-action {类型} in the style of {参照}: {画风、画质、镜头、质感}. {光线}. Physics is believable. Screen direction never flips. Only the subjects defined above appear in the foreground; no text, subtitles, numbers or logos appear on screen unless described.
# (b) 速度：全部是正面描述。动作按真实速度，不要慢动作。
All action happens at real-world speed: strikes, dodges, leaps and impacts are fast, explosive and snappy, like real stunt performers filmed at normal speed; every frame plays at full real-time speed.
# (c) 力量设定：一人一句，颜色 + 光效。
{角色 A}'s power is {颜色 + 光效}; {角色 B}'s power is {颜色 + 光效}.
# (d) 本段规则：谁在场、站在哪、节奏、固定地理、尺度、命中。
The video consists of exactly the shots written below, in that order. The people in this video are {谁}, who {在哪}, and {谁}, who {在哪}. The pace is fast and violent from the first frame to the last and accelerates into the end: every beat is quick, short and snappy, and the video ends in the middle of motion, on an impact. Each shot keeps exactly the time range written for it.
Fixed geography: {场地大小；柱子数量和高度（几个人高）；看台、石碑的位置}. {A} and {B} are ordinary human height; only {召唤物} is colossal. All pillars stay standing. Nothing catches fire unless it is written.
Scale: every wave of energy, explosion, cloud of dust and shockwave is {比参照物还高、横跨场地的一部分，写比例}; {A}'s light is {团 / 片 / 浪，不是线}; {B}'s light is just as big and heavy; never thin beams, never laser lines, never small sparks.
Close combat: weapons clash an arm's length apart and the bodies never touch.
Every hit has four results: a flash and debris, the body flung back, a change of expression, and a lasting mark on the body or the floor.
# (e) 接续（仅接续段）：第一个镜头从上一段结尾的构图出发。
The video begins as a seamless continuation of the previous shot.
# (f) 结构句
The video is {N} shots joined by hard cuts: every cut is a straight cut, with no dissolve, no fade and no transition effect. Every hard cut is stated with its exact time; between hard cuts the camera moves only as described.
# (g) 站位：来自状态表。间距写数字，写明谁都不挪步。
Positions: {A 在画面左 / 右、朝哪、手里拿什么、伤（写在朝向镜头的一侧）}. {B 同理}. {间距：about N strides, about N metres, and nobody moves from these spots}. {场地受损阶段的说法}. Nobody else is on the arena floor.
# (h) 镜头：时间码 + 起始机位 + 运镜 + 每一拍。
[Shot 1] 0.0–{t1} s. The video opens in the middle of the previous shot and continues it seamlessly: {上一段结尾的画面，同一个机位和构图}.
At {t1} s, hard cut.
[Shot 2] {t1}–{t2} s. Framing: {焦段} lens, {高度}, {在谁的哪一侧}, {景别}. {一句话：这个镜头拍什么}.
Camera: {类型 + 幅度 + 速度 + 动机 + 落幅，例：Zoom In at fast speed, a crash zoom onto the collision point, then Shake Strongly as the explosion goes off}.
- {t1}–{t1+a} s: {一个动作，用名字，用画面方向}.
- {t1+a}–{t2} s: {命中：闪光和碎屑 → 被打飞 → 表情 → 留下的伤}. {招牌大招：{角色名} (S{n}), in {声线}, <d>[English]{招式名}!</d>。写在这一拍里最先发生的动作里，因为喊招可能晚于你写的拍点}.
At {t2} s, hard cut.
[Shot 3] {t2}–{t3} s. Framing: ...
Camera: ...
- ...
# 想不切的镜头：写清镜头从哪个机位出发、怎么动、停在哪个构图；不要写 hard cut。
# 最后一个镜头：收在冲击、闪白或被吞没上，不要写 "holds this framing" 这类停住的结尾。
[Shot N] {t(N-1)}–{tN} s. Framing: ...
- ...: {结尾：the frame jolts and floods with white light at the peak of the impact}.

# ---------- 5. 声音 ----------
overall_soundscape:
{每一拍的动作音效，按镜头顺序写；能量声、碎石声、喊招声；脚步声等连续性声音}. No whoosh or transition sound is added at the hard cuts.

# ---------- 6. 配乐 ----------
non_diegetic_music:
N/A
```

## 写完自检

- [ ] 秒数：每个镜头的时间段首尾相接，最后一个镜头的终点 = 本段新内容的秒数
- [ ] 总帧数：（新内容秒数 × 24 + 22）向上取到 17k+5，且 ≤ 260
- [ ] 每个镜头有起始机位和运镜；一段里运镜不重复；镜头被"对手的攻势或冲击波"推开，不是被主角"逼退"
- [ ] 不写 `no slow motion` / `never pauses` / `no freeze frame` / `never ends on a held frame`
- [ ] 间距有数字；持械手有左右和握法；伤写在朝向镜头的一侧
- [ ] 特效尺度写了比例，双方是同一量级；破坏只有小范围；柱子没坏
- [ ] 打斗中除了招牌大招没有台词；招牌大招是英文
- [ ] 占上风的人没有干等；接续开头没写"两人对峙一拍"
- [ ] 真正的大招位置已预留冲击帧：命中是时间码里一个明确的瞬间，结尾收在冲击上
- [ ] 没有"通用规则"里的画面会被当成必须出现的镜头（反应特写、两人互殴）
- [ ] 跑过 `scripts/check_script.py`；用 `scripts/chain_join.py` 处理接缝；验片按 `skills/drama-scenes/references/qc.md`

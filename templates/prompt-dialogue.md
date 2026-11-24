# 文戏提示词模板

用在环节 5（文戏出片）。英文骨架 + 中文注释：**所有以 `#` 开头的行是给你的说明，使用前删掉**；`{花括号}` 换成你的内容。
字段顺序、写法规则见 `skills/drama-scenes/references/prompt-structure.md`，文戏的细则见 `dialogue.md`，运镜见 `camera.md`。配置（不挂任何 LoRA）见 `skills/h3-video/references/recipes.md`。

## 开写前先核对

- [ ] 这一段是文戏：有大段台词、走位、表情；没有招式和命中（有打斗就拆成两段，改用 `prompt-fight.md`）
- [ ] 段长最长 12 秒，在自然的镜头边界结束；镜头 2–5 个，每一刀说得出理由
- [ ] **不写时间码**，事件挂在台词或动作上（"说到最后一个字，她睁开眼"）
- [ ] 站位的句子来自状态表（`state-table.md`），一字未改
- [ ] 出场的人和场景都挂了参考图；没挂参考图的人没写进站位
- [ ] 台词字数 ≤ 可说话秒数 × 4–5；一句不跨镜头；一个镜头只给一个人说话
- [ ] 风格段里没有任何"动作快 / 爆发"的句子

## 模板

```text
# ---------- 1. 主体定义：每个参考图一段，<Subject N> 对应 <Picture N> ----------
subject_definitions:
# 人物：把角色卡里的"外观锁定项"整段复制，含易漂移细节和持械手。
<Subject 1> is {角色卡里的外观锁定项，一字不改}.
<Subject 2> is {另一个角色的外观锁定项}.
# 场景：布局和地标；受损阶段的场景写阶段说法（来自状态表）。
<Subject 3> is {场景：材质、光线、地标、当前受损阶段的说法}.

# ---------- 2. 一句话摘要：镜头数要和正文一致 ----------
summary:
[reference generation] {N} shots: {发生什么，停在哪里}.

# ---------- 3. 主体出现在哪些镜头：改镜头数时要同步改 ----------
retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 2> (appears in [Shot 2]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - the layout, architecture, lighting, and key landmarks are retained.

# ---------- 4. 正文：顺序固定 ----------
detailed_description:
# (a) 风格段：全片逐字相同，每段复制。下面是骨架，换成你自己定稿的那一份。
The target video is a photorealistic live-action {类型} in the style of {参照}: {画风、画质、镜头、皮肤和布料质感}. {光线}. Physics is believable. Screen direction never flips. Only the subjects defined above appear in the foreground; spectators stay in the background as an unnamed crowd; no text, subtitles, numbers or logos appear on screen unless described.
# (b) 平静节奏：文戏不留任何"快"的描述。平静不是慢动作，仍是真实速度。
This is a quiet dramatic scene, not a fight: people move at a natural, unhurried real-world pace, filmed at normal speed; every frame plays at full real-time speed. The pace is calm: people pause between lines, and the camera drifts slowly.
# (c) 力量设定（可选）：一人一句。
{角色 A}'s power is {颜色 + 光效}; {角色 B}'s power is {颜色 + 光效}.
# (d) 本段规则：一两句这场戏的情绪和人物状态。
{这一场戏的情绪；谁此刻在想什么；谁占上风}. Each line is spoken only by the one person in her own shot, and the listener's lips stay closed. The camera stays on the near side of the line between them; nobody looks into the lens.
# (e) 结构句：二选一，保留一个。
The video is {N} shots joined by hard cuts: every cut is a straight cut, with no dissolve, no fade and no transition effect.
# 或（一镜到底）：此时全文所有 "Shot 2"、"hard cut"、"appears in [Shot 2]" 都要删干净，只改一处模型仍会切。
# The whole video is one continuous shot with no cuts.
# (f) 站位：不算镜头。来自状态表，一字不改。间距写具体数字，写明谁都不挪步。
Positions: {A 站在哪、朝哪、手里拿什么、伤成什么样}. {B 同理}. {间距，例：about ten strides, about eight metres, and nobody moves from these spots}. {场地阶段说法}. Nobody else is on the floor.
# (g) 镜头：先写起始机位（焦段、高度、在谁哪一侧、景别），再写运镜；每个镜头一个环境锚点。
[Shot 1] {起始机位：35mm lens, hip height, on the near side, medium-wide, A small and soft at the far left edge}. {发生了什么，用名字不用代词；方位用画面左、右、中央}.
{走位}: she says nothing for four or five steps, then stops about ten strides from {B}, and only then
# 台词格式：名字 (S编号), in 固定声线, says 语气, <d>[Chinese]中文台词</d>
{名字} (S{n}), in {角色卡里的声线，逐字复制}, says {语气}, <d>[Chinese]{中文台词}</d>
{运镜：The camera tracks alongside her at walking speed, slightly handheld, and stops when she stops.}
[Shot 2] Hard cut to {起始机位：85mm, eye level, three-quarter profile from her right side, the other person's shoulder soft at the edge of the frame}. {B 的反应或回答；A 的嘴唇闭着}.
{名字} (S{n}), in {声线}, says {语气}, <d>[Chinese]{中文台词}</d>
{特写里把易漂移的细节再强调一遍：her right eye is blue and her left eye is gold, exactly as in her reference picture.} {运镜：The camera keeps arcing slowly around her.}

# ---------- 5. 声音：环境声和动作音效；连续性声音也写在这里 ----------
overall_soundscape:
{环境声；动作音效；脚步声（高跟鞋 / 厚底鞋）；伤带来的喘息}. No whoosh or transition sound is added at the hard cuts.

# ---------- 6. 配乐：一律 N/A，配乐在后期统一加 ----------
non_diegetic_music:
N/A
```

## 写完自检

- [ ] 没有时间码（`0.0–2.5 s` 这类写法）；没有"fast / explosive / snappy"
- [ ] 每个镜头有起始机位和运镜；一段里运镜不重复；没有人看镜头
- [ ] 每个镜头一个环境锚点（石板、柱子、看台）；没写"淡淡尘雾"
- [ ] 每个说话人一句固定声线，原样复制；倾听者嘴唇闭着
- [ ] 伤、持械手、脚步声都重写了一遍（上一段的不会自动带过来）
- [ ] 下一段要演的事，这一段只给引子（一件事只在一段里演）
- [ ] 停在完整节点，下一段可以硬切；结尾站位已抄进衔接表
- [ ] 跑过 `scripts/check_script.py`；中文逐句翻译已生成给人审

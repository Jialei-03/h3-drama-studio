# 两段提示词原文

这里放作者这部片里两段真实用过的提示词，各一段文戏、一段武戏，对应仓库首页 `assets/` 里的两段示例视频：文戏 `f10`（take 640，视频就是它）、武戏 `f7`（take 572，视频是成片版 t580，开头约 2 秒来自它，其余来自另一次生成，见第二节开头的说明）。英文是出片时原样送进 H3 的文本，没有改过一个词；每个镜头后面附一句中文说明，方便对照读。

- **只放这两段。** 其余各段的提示词不公开；想要结构，看 `templates/prompt-dialogue.md` 和 `prompt-fight.md`，想看怎么用数据文件生成，看 [data/](data/)。
- **版本是确切的，但对应关系不完全一样。** 两段都是从当时队列的 `shots.json` 里按 `id` 加 `take` 取出来的。文戏逐帧核对过：`assets/dialogue.mp4` 就是 f10 的 t640。武戏不是：`assets/fight.mp4` 是成片版 t580，由 t572 的开头 47 帧（1.96 秒，逐帧比对一致）加另一次生成的镜头拼成，这里放的是 t572 的提示词，所以视频后半和提示词对不上，详见第二节开头。两段视频都剪掉了开头 22 帧接续帧，压成 720p。
- **做过的处理**：提示词正文没有删改（里面本来就没有路径或个人信息）。`shots.json` 里的其他字段（模型和 LoRA 的文件名、参考图的文件名、主机上的路径）没有放进来，参考图在表里换成了描述。
- **读法**：字段顺序、写法规则见 `skills/drama-scenes/references/prompt-structure.md`。台词里的 `[Chinese]` / `[English]` 是语言标记，`<d>…</d>` 里是台词。`<Subject N>` 对应第 N 张参考图 `<Picture N>`。
- **别照抄剧情**：这些是为这部片的角色、场地和上一段结尾量身写的。要抄的是写法。

---

## 一、文戏：f10，take 640（战后，认输）

| 项 | 值 |
|---|---|
| 内容 | 战后：Gemini 拉起落败的 GPT；GPT 说下一次会赢回来，Gemini 说随时奉陪；看台欢呼 |
| 种子 | 7790 |
| 长度 | 新内容 9.9 秒；渲染 260 帧，含开头 22 帧接续帧，拼接时剪掉，成片里 238 帧 |
| 接续自 | f9b 的 t563（`ctx`，上一段末尾 22 帧加音频） |
| 参考图 | 3 张：Gemini 定妆图、GPT 定妆图（都是不带大特写的旧版）、战后擂台场景图 |
| 配置 | 专属二采：一采 1024×576 → 潜空间放大 → 1536×864；**不挂任何 LoRA** |
| 生成用时 | 1203 秒（约 20 分钟） |

```text
subject_definitions:
<Subject 1> is the young East Asian actress playing Gemini in <Picture 1>, about twenty, with a cold, beautiful, serious face that does not smile; voluminous wavy hair dyed from blue to violet, two small hair buns topped with furry cat ears, a metal four-pointed star ornament at her temple, heterochromatic eyes exactly as in her reference picture, her right eye blue and her left eye gold, in every close-up, with no stars or glow in them; an off-shoulder purple-and-white cropped top that leaves her shoulders and collarbones bare, with no collar and no high neck, with wide flowing sheer purple sleeves, a frilled white-and-purple short skirt, a furry blue-to-violet cat tail, white slouch leg warmers and purple platform shoes; she fights bare-handed and never holds a sword or any weapon.
<Subject 2> is the young East Asian actress playing GPT in <Picture 2>, about twenty-three, tall, regal and arrogant: a white-dragon woman with floor-length wavy silver-white hair, a pair of white curved dragon horns with small white flowers, pointed ears, pale violet eyes, an off-shoulder white ruffled long gown with sheer ruffled long sleeves and a floor-length skirt, membranous pale lavender-white dragon wings, a white scaled dragon tail, and one long straight double-edged longsword exactly as in her reference picture: a solid polished steel blade as long as her leg with a faint silver-lavender glow along its edges, a silver cross-guard and a silver hilt; it is real metal, never a beam of light and never a thin light-saber, and it keeps exactly the same shape and length in every shot; she always holds the longsword in her right hand with a normal forward grip, the blade extending from the thumb side of her fist, never a reverse grip and never in her left hand.
<Subject 3> is the same floating circular stone dueling arena from <Picture 3> after the duel, a real location: the weathered granite disc above a sea of clouds at sunset, all eight black iron-stone pillars standing whole, their blue flames blown out, thin dark smoke rising from their tops, the banners gone from the bare flagpoles, the packed stands and the tall stele; the floor is still one solid, level stone floor; the only damage is one long straight shallow trench of broken grey stone and loose rubble, ankle-deep, on the left half of the floor, and one shallow round dent about four strides across near the center where the slabs are cracked outward in rings and a few are tilted up; small scattered stones lie across the floor; everything is dry grey stone; the air is clear.

summary:
[reference generation] The video continues straight on from the previous shot, GPT kneeling in the dent looking at Gemini's outstretched hand. Six hard-cut shots: GPT takes the hand and Gemini pulls her up out of the dent; standing, GPT holds out her right hand and calls her longsword back to her with dragon light, and it flies up off the stone into her grip; GPT alone, vowing to win next time; Gemini alone, accepting with the faintest smile; from behind Gemini, GPT turns and walks away across the floor as the whole stands erupt in cheers.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 5], [Shot 6]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 4], [Shot 6]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 3> (appears in [Shot 2], [Shot 4], [Shot 6]): fully_preserved - the layout, architecture, lighting, and key landmarks are retained.

detailed_description:
The target video is a photorealistic live-action superhero fantasy blockbuster in the style of a Marvel Studios film: real actresses in practical, tailored costumes, shot on large-format digital cinema cameras with anamorphic lenses and combined with seamless high-end visual effects. Faces are real human faces with natural proportions, visible skin texture, fine pores, subtle imperfections and real micro-expressions; hair is real dyed hair with individual strands that catch the light; costumes are real fabric, lace, leather and metal with stitching, creases and wear. Animal ears, dragon horns, wings and tails are flawless prosthetic and creature-effects work that sits naturally on the actresses. Energy effects such as starlight, dragon light and shockwaves are photoreal VFX that cast real light onto faces, costumes and the environment. It is absolutely not anime, not cartoon, not 3D game CG and not illustration. The lighting is cinematic: golden-hour backlight with warm rim light, atmospheric haze, volumetric light shafts, deep contrast, natural film grain, and shallow depth of field with real focus pulls. This is a quiet dramatic scene, not a fight: people move at a natural, unhurried real-world pace, filmed at normal speed; every frame plays at full real-time speed. Physics is believable: hair, cloth, dust, water and debris react to wind, impacts and gravity with real weight and timing. Screen direction never flips: a character who is knocked back slides backward while still facing her attacker and never turns her back to her. Only the subjects defined above appear in the foreground; spectators stay in the background as an unnamed crowd; no text, subtitles, numbers or logos appear on screen unless described. Gemini's power is blue-to-violet starlight; GPT's power is silver-lavender dragon light. The duel is over. Gemini is at screen left facing right; GPT is at screen right facing left. The camera stays on the near side of the line between them; nobody looks into the lens. Each line is spoken only by the one woman in her own shot. The video begins as a seamless continuation of the previous shot. Every hard cut is stated with its exact time; between hard cuts the camera moves only as described.
Positions: <Subject 3> after the duel: the pillars stand dark with only thin smoke rising from their tops, the banners are gone, the only damage is the long shallow trench on the left half and the shallow cracked dent near the center. Golden sunset light, the low sun at screen right, warm rim light, the air clear. <Subject 1> stands at screen left at the edge of the shallow dent, holding out her right hand to the right. Gemini's right sleeve (on the side facing the camera) is torn open at the shoulder, a thin bleeding cut runs across her right cheekbone, dust is smeared on her face and her hair is disordered. <Subject 2> kneels in the dent at screen right. GPT's gown is scorched and torn, her sheer sleeves and skirt hem are burned to tatters, her left wing is torn and hanging, blood runs from the left corner of her mouth, and her longsword lies on the stone beside her, whole; there is no other sword anywhere. The stands are packed with spectators far beyond the arena wall; nobody else is on the arena floor.
[Shot 1] 0.0–0.6 s. The video opens in the middle of the previous shot and continues it seamlessly: GPT kneeling in three-quarter profile at screen right, her right hand resting on the hilt of her longsword lying on the stone beside her, Gemini's outstretched right hand soft in the left foreground. The camera is static.
At 0.6 s, hard cut.
[Shot 2] 0.6–2.8 s. A side-on medium two-shot at eye level framing both women from the waist up only, Gemini at screen left and GPT at screen right; the floor and the longsword are below the bottom of the frame and never seen in this shot. The camera is static.
- 0.6–2.8 s: GPT, blood still at the left corner of her mouth, reaches up with her empty right hand and takes Gemini's right hand, and Gemini pulls her up to her feet; both sway with exhaustion and steady each other, then let go.
At 2.8 s, hard cut.
[Shot 3] 2.8–3.8 s. A close-up low on the cracked stone: the longsword lying flat on the stone, whole, its silver hilt toward the camera; nobody is in this shot and no hand or body enters the frame. The camera is static.
- 2.8–3.8 s: a thread of silver-lavender dragon light curls around the hilt; the longsword lifts off the stone and swings upright so that its point faces straight up to the sky and its hilt is at the bottom, then rises straight up point-first out of the top of the frame on its own, leaving a faint silver trail; from this moment on the blade always points straight up and the sword never rotates, tumbles or flips.
At 3.8 s, hard cut.
[Shot 4] 3.8–6.2 s. A medium close-up of <Subject 2> alone, standing, in three-quarter profile facing screen left, a thin trickle of blood running from the left corner of her mouth down to her chin and dust smudged on her cheek, exactly as at the end of the duel, the scarred floor blurred behind her. The camera is static.
- 3.8–4.4 s: her right hand is held out low at her side, palm open; the longsword rises up into the frame from below, point first and perfectly upright, blade pointing straight up the whole time and never turning or flipping, and its grip slides up into her open right hand; she closes her fingers around the grip in a normal forehand grip, thumb toward the blade, the blade pointing straight up above her fist, clear of her body, wing and hair, a little silver light fading off the blade.
- 4.4–6.2 s: she holds the sword in the same forehand grip in her right hand, blade still pointing straight up beside her shoulder, the blade beside her and touching nothing; a glint of fierceness returns to her eyes, the blood still bright at the left corner of her mouth, and GPT (S2), in a mature young female voice, smooth and elegant, arrogant and slightly drawling, says, <d>[Chinese]下一次，我会赢回来。</d>
At 6.2 s, hard cut.
[Shot 5] 6.2–7.6 s. A close-up of <Subject 1> alone in three-quarter profile facing screen right, the stands blurred behind her. The camera is static.
- 6.2–7.6 s: the faintest smile in her eyes, Gemini (S1) answers in her own voice, the same voice as all her earlier lines: a young woman of about twenty, a cool, clear, light mid-range voice, steady and restrained, a little hoarse after the fight, clearly younger, lighter and brighter than GPT's smooth, drawling, mature voice; she says, <d>[Chinese]随时奉陪。</d>
At 7.6 s, hard cut.
[Shot 6] 7.6–9.9 s. A wide shot from low behind Gemini, her back in the lower left of the frame on the scarred floor; GPT is at screen right a few steps away, the packed stands ringing the arena ahead. Camera: Crane Up at slow speed, rising up and back over the floor.
- 7.6–9.9 s: GPT, her mouth still bloodied, turns away and walks off toward the far right edge of the floor, her torn wings folded and her longsword in her right hand, without looking back; Gemini stays where she is, watching her go; the whole crowd leaps to its feet at once, erupting in cheers, arms thrown up into the air, bathed in golden sunset light.

overall_soundscape:
Wind and breathing; a hand gripping a hand, rubble crunching as GPT is pulled up, a soft rising hum as the blade lifts off stone and a clean metallic slap as the hilt lands in her palm; a fierce voice; a quiet answer; then the whole arena erupting in cheers, applause and whistles. No whoosh or transition sound is added at the hard cuts.

non_diegetic_music:
N/A
```

### 逐镜头说明

| 镜头 | 时间 | 说明 |
|---|---|---|
| Shot 1 | 0.0–0.6 s | 接上一段：GPT 跪在浅坑里，手搭在剑柄上，Gemini 伸出的右手虚化在左前景；镜头不动。 |
| Shot 2 | 0.6–2.8 s | 侧面双人中景（只拍到腰）：GPT 握住 Gemini 的手被拉起来，两人摇晃着互相扶稳后松手；地面和剑在画外，这一镜不让剑出现。 |
| Shot 3 | 2.8–3.8 s | 贴地特写：地上的剑被一缕银紫色龙光缠住，自己立起、剑尖朝天，从画面上方飞出；画面里没有人、没有手。 |
| Shot 4 | 3.8–6.2 s | GPT 单人中近景：剑从画面下方升起，握柄落进她张开的右手（正手握，剑尖朝天）；她说"下一次，我会赢回来"。 |
| Shot 5 | 6.2–7.6 s | Gemini 单人近景，眼里一点极淡的笑，用自己的声线回答"随时奉陪"。 |
| Shot 6 | 7.6–9.9 s | 低机位广角，摇臂缓慢升起后退：GPT 转身走向场地右缘、不回头，Gemini 留在原地目送，全场起立欢呼。 |

### 这一段值得看的写法

- **每个镜头都说清"这一镜里有谁、没有谁"**（Shot 2 没有剑，Shot 3 没有人）。因为写了的东西都会被画出来，不想出现的东西，要么一个字不写，要么像这里一样明说画外。
- **剑的物理逻辑写成一条规则**：Shot 3 里"剑尖始终朝上，从此刻起不旋转、不翻转"，Shot 4 里正手握、剑身不碰身体、翅膀和头发。这类写法是为了防止剑飘起来时自己翻转、被画成反手握。
- **伤和连续性每段重写**：GPT 嘴角的血、烧焦的礼服、撕裂的左翼，Gemini 袖子的撕口和颧骨的伤，都写在 `Positions` 里；"剑躺在石头上，完好，别处没有另一把剑"。
- **声线逐字沿用**：GPT 的声线一句固定的话；Gemini 的声线那句里还加了"和她前面所有台词是同一个声音"，并拿 GPT 的声线做对照，避免两个人的声音串。
- **倾听者闭嘴**：每句台词只在说话人自己的镜头里出现，一个镜头一个人说话。
- **风格段里没有"动作快"**：写的是"这是一场安静的戏，不是打斗，人以自然的、不慌不忙的真实速度移动"。这是 dialogue.md 里"复制武戏提示词时要删干净速度句"的做法。
- **时间码**：这一段**写了每个镜头的起止时间**（`0.6–2.8 s`）和每次硬切的时间，和 dialogue.md 里"文戏不写时间码"不是一回事：那条规则说的是不要给事件（睁眼之类）写秒数，让动作挂在台词上。推测是因为这是接续段，镜头多、每个只有一两秒，需要固定切点；镜头里的动作仍然是按先后写的。是否必须这样，没有对照过 [未验证]。`scripts/check_script.py` 对文戏段里的时间码只给警告。
- **接续**：开头一句 `The video begins as a seamless continuation of the previous shot`，第一个镜头照上一段结尾的机位写。

---

## 二、武戏：f7，take 572（Supernova，银龙挡炮）

> **先说清楚：示例视频和这一节的提示词不是一一对应的。** `assets/fight.mp4` 是成片里实际用的 f7 版本 t580（9.4 秒），它不是一次生成出来的，而是两次生成的镜头拼成：开头来自 t572，之后换成另一次生成的镜头。下面放的是 t572 的提示词，所以视频的后半和这条提示词不完全一致。
>
> **分叉点在 1.96 秒（第 47 帧，24 fps）。** 量法：把 `assets/fight.mp4` 和 t572 的成片段（同样剪掉了开头 22 帧接续帧，238 帧）都缩到 64×36 灰度，逐帧算两者的平均绝对差（满分 255）。第 0–46 帧平均差都不超过 0.6（只是压缩和缩放的噪声），也就是前 47 帧、0 到 1.96 秒两者是同一段画面；第 47 帧起平均差跳到 37，之后始终在 28 以上。第 46 帧是 GPT 举着剑、镜头仰向天空的画面，第 47 帧起是 Gemini 在高空的侧面镜头。拼接点落在一个硬切上；t572 自己也是在这一帧从 GPT 视角切到 Gemini 的高空镜头（比它的提示词写的 2.6 秒早了约 0.6 秒）。
>
> 所以：视频的前 2 秒（Shot 1 和 Shot 2 的大部分）是这条提示词出的片；之后约 7.4 秒来自另一次生成，它的镜头切点和时长都和下面的提示词对不上（t572 整段 9.9 秒，视频只有 9.4 秒）。**首轮留用的 t534（剑断结局）后来被替换掉，不是成片里的版本，所以这里不再放它。** 选 t572 而不是 t580，是因为 t580 不在队列记录里、没有提示词可查，而 t572 是 [timeline.md](timeline.md) 第三节记载的"光球一瞬间出现"的那一版，视频开头就出自它。

| 项 | 值 |
|---|---|
| 内容 | 打戏高潮：Gemini 的分身汇回真身，光球在一瞬间出现，她喊出 Supernova，光球塌成炮柱；GPT 召出银龙盘身挡炮，光柱砸场，龙身炸开，被白光吞没 |
| 种子 | 7720 |
| 长度 | 新内容 9.9 秒；渲染 260 帧，含开头 22 帧接续帧，拼接时剪掉，成片段 238 帧 |
| 接续自 | f6c 的 t537（`ctx`，上一段末尾 22 帧加音频） |
| 参考图 | 4 张：Gemini 定妆图、GPT 定妆图（都是带大头肩特写 + 三视图的新版）、擂台场景图（完好阶段）、银龙概念图 |
| 配置 | 专属二采；武戏 LoRA 链 5 个：DMAD 0.8、MysticXXX 0.35、速度滑块 3、H3_Combat_V2 0.65、Motion_Repair_V2 0.35（见 `skills/h3-video/references/lora.md`） |
| 生成用时 | 1603 秒（约 27 分钟） |
| 示例视频里用到的部分 | 开头 47 帧（0–1.96 秒），其余来自另一次生成 |

```text
subject_definitions:
<Subject 1> is the young East Asian actress playing Gemini in <Picture 1> (her face exactly as in the large close-up on the left of that picture, her costume as in the three full-body views on the right), about twenty, with a cold, beautiful, serious face that does not smile; voluminous wavy hair dyed from blue to violet, two small hair buns topped with furry cat ears, a metal four-pointed star ornament at her temple, heterochromatic eyes exactly as in her reference picture, her right eye blue and her left eye gold, in every close-up, with no stars or glow in them; an off-shoulder purple-and-white cropped top that leaves her shoulders and collarbones bare, with no collar and no high neck, with wide flowing sheer purple sleeves, a frilled white-and-purple short skirt, a furry blue-to-violet cat tail, white slouch leg warmers and purple platform shoes; she fights bare-handed and never holds a sword or any weapon.
<Subject 2> is the young East Asian actress playing GPT in <Picture 2> (her face exactly as in the large close-up on the left of that picture, her costume as in the three full-body views on the right), about twenty-three, tall, regal and arrogant: a white-dragon woman with floor-length wavy silver-white hair, a pair of white curved dragon horns with small white flowers, pointed ears, pale violet eyes, an off-shoulder white ruffled long gown with sheer ruffled long sleeves and a floor-length skirt, membranous pale lavender-white dragon wings, a white scaled dragon tail, and one long straight double-edged longsword exactly as in her reference picture: a solid polished steel blade as long as her leg with a faint silver-lavender glow along its edges, a silver cross-guard and a silver hilt; it is real metal, never a beam of light and never a thin light-saber, and it keeps exactly the same shape and length in every shot; she always holds the longsword in her right hand with a normal forward grip, the blade extending from the thumb side of her fist, never a reverse grip and never in her left hand.
<Subject 3> is the floating circular stone dueling arena from <Picture 3>, a real location: a colossal disc of weathered granite hanging above a sea of clouds at sunset, its floor made of huge cracked, worn stone slabs with moss in the joints and ancient circuit-like grooves carved into them that glow only faintly blue; eight towering black pillars of rough, rust-streaked iron-stone fins, smoke-stained, with blue flames burning on top; Colosseum-like tiered stone stands packed with spectators; and a tall ancient stone stele with a column of faintly glowing stone plaques at the edge; thin streams of water spill from its rocky underside into the clouds.
<Subject 4> is the Silver Dragon from <Picture 4>, GPT's summoned creature: a colossal eastern dragon made entirely of dense, glowing silver-white light and thousands of glittering scale-shaped particles, a long serpentine body far longer than the arena is wide, a mane and spines streaming like white fire, glowing eyes and a wide fanged jaw; it is light, not flesh, not fire and not a thin beam.

summary:
[reference generation] The video continues straight on from the previous shot, a view straight down on GPT inside a spinning ring of Gemini's afterimages. Seven hard-cut shots: the ring from above; the afterimages whip up into the sky and converge into one point; Gemini snaps back into one body high above and in one instant a sphere of violet energy wider than the arena bursts into being above her hands; she shouts the name of her attack and the sphere collapses into a cannon beam of light; GPT summons her dragon to coil around her as a shield against the beam; the beam pounds the arena with tremendous violence; the coils burst and light swallows her.

retention_analysis:
<Subject 1> (appears in [Shot 3], [Shot 4]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 2> (appears in [Shot 2], [Shot 4], [Shot 5]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.
<Subject 3> (appears in [Shot 2], [Shot 3], [Shot 4], [Shot 5]): fully_preserved - the layout, architecture, lighting, and key landmarks are retained.
<Subject 4> (appears in [Shot 5], [Shot 6], [Shot 7]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.

detailed_description:
The target video is a photorealistic live-action superhero fantasy blockbuster in the style of a Marvel Studios film: real actresses in practical, tailored costumes, shot on large-format digital cinema cameras with anamorphic lenses and combined with seamless high-end visual effects. Faces are real human faces with natural proportions, visible skin texture, fine pores, subtle imperfections and real micro-expressions; hair is real dyed hair with individual strands that catch the light; costumes are real fabric, lace, leather and metal with stitching, creases and wear. Animal ears, dragon horns, wings and tails are flawless prosthetic and creature-effects work that sits naturally on the actresses. Energy effects such as starlight, dragon light and shockwaves are photoreal VFX that cast real light onto faces, costumes and the environment. It is absolutely not anime, not cartoon, not 3D game CG and not illustration. The lighting is cinematic: golden-hour backlight with warm rim light, atmospheric haze, volumetric light shafts, deep contrast, natural film grain, and shallow depth of field with real focus pulls. All action happens at real-world speed: strikes, dodges, leaps and impacts are fast, explosive and snappy, like real stunt performers filmed at normal speed; every frame plays at full real-time speed. Physics is believable: hair, cloth, dust, water and debris react to wind, impacts and gravity with real weight and timing. Screen direction never flips: a character who is knocked back slides backward while still facing her attacker and never turns her back to her. Only the subjects defined above appear in the foreground; spectators stay in the background as an unnamed crowd; no text, subtitles, numbers or logos appear on screen unless described. Gemini's power is blue-to-violet starlight; GPT's power is silver-lavender dragon light. The video consists of exactly the shots written below, in that order. The people in this video are Gemini, who stays high in the open sky for the whole video, and GPT, who stays on the arena floor beside the shallow trench for the whole video; GPT is seen from behind, from the side or from below. The pace is fast and violent from the first frame to the last and accelerates into the end: every beat is quick, short and snappy, and the video ends in the middle of motion, on an impact. Each shot keeps exactly the time range written for it. Fixed geography: the round floating stone arena is about 120 metres across; eight black pillars, each about seven times a person's height, stand around its rim with blue flames on top; the ancient stele stands on the far rim; the packed tiered stands ring it. Gemini and GPT are ordinary human height. All eight pillars stay standing; the cracks in the floor are dark, dry grey stone. Everything is on a huge scale, measured against the black pillars (each about five times a person's height) and the stands: every wave of energy, explosion, cloud of dust and shockwave is taller than a pillar and covers a large part of the arena. Nothing catches fire unless it is written. GPT's silver-lavender light is dense and glittering like liquid metal and scattering scales, not fire and not a thin beam; her slashes fly as broad crescent waves taller than a pillar and wide enough to span half the arena. Gemini's blue-violet starlight is just as big and heavy: it erupts from her hands as huge blazing masses of dense star-fire, each star-bolt a sphere as big as a person trailing a comet tail as wide as a door, her volleys pouring out like a wide river of light that fills a third of the frame; never thin beams, never laser lines, never small sparks, not fire and not lightning. No text appears in the picture. The video is 7 shots joined by hard cuts: every cut is a straight cut, with no dissolve, no fade and no transition effect. The video begins as a seamless continuation of the previous shot. Every hard cut is stated with its exact time; between hard cuts the camera moves only as described.
Positions: GPT is on the floor near the center beside the shallow trench the whole time; Gemini is high in the sky above the arena. Nobody else is on the arena floor. The arena stays whole: all eight black pillars stand with blue flames on top; the only damage is one long shallow trench of broken grey stone and loose rubble on the left half of the floor, ankle-deep, dry and grey, a few cracked slabs, and a thin haze of settling dust.
[Shot 1] 0.0–0.6 s. The video opens in the middle of the previous shot and continues it seamlessly: straight down from high above, <Subject 2> small in the middle of a spinning ring of blue-violet afterimages, slashing wildly.
At 0.6 s, hard cut.
[Shot 2] 0.6–2.6 s. Framing: an 18mm ultra-wide lens low behind GPT's left shoulder beside the shallow trench, tilted up, her back and raised head in the lower right, the ring of afterimages around her, open sky above. Low behind <Subject 2> beside the shallow trench, looking up past her shoulder, the ring of afterimages around her.
Camera: Tilt Up with large amplitude at fast speed, chasing the streaks of light from the floor straight up into the sky until they meet in one point.
- 0.6–2.6 s: the ring of afterimages turns into lines of light that whip upward past GPT into the sky; the camera tilts up with them and they converge into one tiny point of light high above the arena.
At 2.6 s, hard cut.
[Shot 3] 2.6–5.1 s. Framing: a 35mm lens in the open sky at Gemini's height, exactly side-on, a medium-wide frame, the arena small far below at the lower right. <Subject 1> is seen strictly in profile from her left side, facing screen right, her face turned toward the arena below and never toward the camera.
Camera: holds on her, then at 4.0 s, at the instant the sphere appears, the camera is blasted backward in one violent jolt, a snap pull-out that brings the whole colossal sphere into frame, then shakes.
- 2.6–3.6 s: the streaks slam into her from every direction and she snaps into one solid body, hair and sleeves whipping.
- 3.6–4.0 s: she throws both arms up over her head, one tiny bright violet spark between her palms.
- 4.0–5.1 s: in a single instant, with a sharp ringing ping and a blinding flash, the spark bursts into a colossal sphere of violet energy already at its full size, wider than the whole arena; it does not grow, it is simply there at once, and the blast of its appearance whips her hair and sleeves back; it hangs above her crackling with starlight.
At 5.1 s, hard cut.
[Shot 4] 5.1–7.6 s. Framing: a 14mm ultra-wide lens on the floor right beside GPT, pointing straight up, her shoulder, wing and raised sword at the bottom edge of the frame, the sky filling the rest. On the arena floor right beside <Subject 2>, looking straight up past her shoulder and raised sword.
Camera: Static Shot pointing straight up, shuddering harder and harder as the sphere fills the sky and the wind slams down; when the beam falls it rushes straight into the lens.
- 5.1–6.1 s: the colossal violet sphere fills the entire sky and blots out the sunset; the whole arena drops into its violet shadow; a downward blast of wind flattens GPT's hair and wings and lifts dust and pebbles off the floor.
- 6.1–6.8 s: far above, Gemini is a small dark silhouette against the sphere; she thrusts both arms down and roars in one short burst, Gemini (S1), in a young female voice around twenty, cool and clear mid-pitch, calm and measured pace, <d>[English]Supernova!</d>
- 6.8–7.6 s: the sphere collapses into a colossal cannon beam of violet light, wider than three pillars, that slams straight down at GPT and the camera with tremendous violence, the air around it rippling and the clouds blasted apart.
At 7.6 s, hard cut.
[Shot 5] 7.6–8.8 s. Framing: a 24mm wide lens at knee height beside GPT, exactly side-on, framing her from the knees up in profile facing screen left, her face tilted up toward the beam and never toward the camera, a slight Dutch tilt.
Camera: Handheld, Shake Strongly and more violently with every blow, pushed down lower and lower by the weight of the beam.
- 7.6–8.2 s: GPT thrusts her longsword straight up in her right hand and the colossal Silver Dragon bursts out of the blade and wraps itself around her in tight glowing coils, its scales locking together into a living shield over her head.
- 8.2–8.8 s: the beam crashes onto the dragon's coils with tremendous violence; violet fire sprays off the silver scales, the dragon roars, rings of shockwave blast outward, the slabs under GPT's feet crack outward in rings and debris flies up; she cries out with effort, her knees buckling.
At 8.8 s, hard cut.
[Shot 6] 8.8–9.4 s. Framing: an extreme wide low shot across the arena floor, the beam a colossal pillar of violet light crashing into the middle of the arena, the glowing coils of the dragon just visible inside it.
Camera: Static, shaking violently.
- 8.8–9.4 s: the beam pounds down harder still; the floor around it buckles into a shallow dent; shockwave after shockwave and a ring of dust and debris explode outward across the floor toward the camera.
At 9.4 s, hard cut.
[Shot 7] 9.4–9.9 s. Framing: the same side-on view of GPT from the knees up, in profile, inside the dragon's coils.
- 9.4–9.9 s: the dragon's coils burst apart into scattering silver light and she is swallowed by the violet-white light, which floods the whole frame.
overall_soundscape:
A rising chorus of whooshes streaking upward; comet-like impacts converging into one deep thrum; a sharp crystalline ping and an instant thunderclap as the sphere bursts into being; a swelling, crackling roar of gathering energy and a howling downdraft; a roared shout far above and a thunderous, deepening roar as the beam falls; a dragon's roar, a grinding scream of energy on scales, stone cracking in rings and a strained cry; crushing booms of shockwaves and a swelling roar of light to a deafening peak. No whoosh or transition sound is added at the hard cuts.

non_diegetic_music:
N/A
```

### 逐镜头说明

| 镜头 | 时间 | 说明 |
|---|---|---|
| Shot 1 | 0.0–0.6 s | 接上一段：正上方俯拍，GPT 站在一圈旋转的蓝紫色残影中央，疯狂挥砍。 |
| Shot 2 | 0.6–2.6 s | 18mm 超广角，在 GPT 左肩后低位仰拍；镜头急速上摇，残影变成光线甩向天空，汇成一个点。 |
| Shot 3 | 2.6–5.1 s | 35mm 高空侧面中远景，Gemini 严格侧脸：残影从四面八方撞进她身体合成一个人，她双臂上举，掌间只有一颗极小的紫色火花；4.0 秒时火花在一瞬间炸成已经是满尺寸、大过整座擂台的紫色能量球（不是慢慢长大），镜头被冲击波猛地向后拉开。 |
| Shot 4 | 5.1–7.6 s | 14mm 贴着 GPT 的肩膀垂直向上仰拍：球占满天空，擂台落进紫色阴影，下压的风掀起尘土；Gemini 在高处喊 "Supernova!"（英文，动作中途一口气喊出）；球塌成比三根巨柱还宽的炮柱，带着巨大的暴力感砸向 GPT 和镜头，空气扭曲、云被炸开。 |
| Shot 5 | 7.6–8.8 s | 24mm 膝盖高度的侧面（GPT 脸朝上、不朝镜头，轻微荷兰角）：她把剑向上一举，银龙从剑身里冲出来，一圈圈盘住她，鳞片锁成头顶的活盾；光束砸在龙身上，紫色火花从银鳞上溅开，冲击波一圈圈炸开，她脚下的石板裂开，她喊出声、膝盖发软。 |
| Shot 6 | 8.8–9.4 s | 贴着擂台地面的极端广角低机位：光束像一根巨柱砸进擂台中央，龙发光的盘身隐约可见在光束里；地面被压成一个浅坑，冲击波和一圈尘土碎石朝镜头炸来；机位不动、剧烈震动。 |
| Shot 7 | 9.4–9.9 s | 回到 GPT 膝盖以上的侧面，她还在龙身盘绕之中；龙身炸成四散的银光，她被紫白色的强光吞没，画面闪白收尾。 |

### 这一段值得看的写法

- **第一帧就是全速动作，结尾收在冲击上**：风格段写"从第一帧到最后一帧又快又猛，越到结尾越快，视频在冲击中结束"，最后一个镜头收在龙身炸开、白光吞没。
- **速度只用正面描述**：写的是"每一帧都按真实速度播放""每一拍又短又脆"；没有 `no slow motion`、`never pauses` 这类否定写法。
- **Shot 2–6 每个镜头一行起始机位（`Framing`）、一行运镜（`Camera`）**，再按时间码写每一拍；Shot 1 接上一段，Shot 7 沿用 Shot 5 的机位（只写 `Framing`，没有 `Camera`）。没有用关键帧，第一帧的构图全靠 `Framing` 这一句。
- **`The video consists of exactly the shots written below, in that order`** 加上"这段里的人是谁、各在哪"（Gemini 全程在高空，GPT 全程在地面浅沟旁）：防止通用规则里的画面（反应特写、两人互殴）被当成必须出现的镜头。
- **"一瞬间出现"要明说"不是慢慢长大"**：Shot 3 先写火花（3.6–4.0 s 掌间只有一颗小火花），再写"在一个瞬间……炸成已经是满尺寸的球，它不会变大，它一下子就在那里"，同一个时间点（4.0 s）上镜头被冲击波猛地拉开，声音段里同步写了一声清脆的"叮"和一声霹雳。对照首轮 t534 写的是球"越变越大"。这样写之后每次是否都画得出来，没有统计过 [未验证]。
- **召唤物单独给一条主体描述和一张参考图**：这一版多挂了第 4 张参考图，`<Subject 4>` 是银龙，描述里写明"它是光，不是血肉、不是火、不是细光线"，并在 `retention_analysis` 里列出它出现在 Shot 5–7。龙在 Shot 5 的 7.6–8.2 s 从剑身里冲出来，8.2 s 起才被光束砸中，先召唤后受击，分在两条时间码里。
- **尺度写成比例**：球"大过整座擂台"，炮柱"比三根巨柱还宽"；风格段里还规定"能量是团、片、浪，不是线"。
- **人物不看镜头**：Shot 3、5 明写了"严格侧脸""脸朝向光束、绝不朝向镜头"，Shot 7 沿用同一个侧面。
- **招牌大招是唯一的台词**，英文，写在这一拍最先发生的动作里（`roars in one short burst`），不能站定了念。
- **接续**：开头一句 `The video begins as a seamless continuation of the previous shot`；`Positions` 里的地面状态来自状态表：只有一条浅沟、柱子都立着；这一段两人一个在天上、一个在地上，所以没有间距数字。
- 提示词里 `<Subject 1>`、`<Subject 2>` 的描述前面带了"脸照左边大特写，服装照右边三视图"的分工句，因为这一段挂的是带大特写的新版定妆图（f10 挂的是旧版，所以没有这句）。

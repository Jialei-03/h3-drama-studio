# 文戏方案

什么时候读：这一段以对话、走位、表情、情绪为主（没有招式和命中）时。有打斗的段读 [fight.md](fight.md)；同一段里既有长台词又有打斗，就拆成两段，因为打斗中一有台词，H3 就会让人站住对口型，动作立刻停了。

可信度标注：【已验证】多次出片确认；【单次实测】只在一两段上看到；【未验证】推断或没对照过。

## 一、配置

文戏和武戏的采样配置相同（专属二采：一采 1024×576、10 步 → 潜空间放大 ×1.5 → 1536×864 二采），**文戏不挂任何 LoRA**，参考图只给人物定妆图和场景图。配置细节见 [../../h3-video/references/recipes.md](../../h3-video/references/recipes.md)。

为什么文戏不挂 LoRA：战后几段对话带着 LoRA 出片，看片后觉得“有的比较模糊，没有打戏之前的画质好”；文戏改回打戏之前的配置（不挂任何 LoRA），武戏 LoRA 链只留给打戏段。武戏链是为打戏的速度和动作调的，文戏用不上。【单次实测，2026-11-21】

## 二、段长、镜头数、时间码

| 项 | 规则 | 为什么 |
|---|---|---|
| 段长 | 最长 12 秒，在自然的镜头边界结束 | 8 秒的镜头演完就结束这一段，不要为了凑满再塞一个 2 秒镜头，也不要靠拉长动作撑时长（曾经有一段为了撑满时长，人物一直在跑）。12 秒是作者定的上限，原因没有记录，更长的段没试过【未验证】 |
| 镜头数 | 2–5 个，每个镜头 2–4 秒 | 每一刀要说得出理由：新信息、换人说话、看反应、距离或朝向变化、关键事件。说不出理由就不切 |
| 不按固定秒数切 | — | 做过 7 个镜头、1.5 秒一切的版本，节奏完全照办，但被评价“切屏太快，很多是无意义的切屏”，还出现叠化、参考图闪现 0.17 秒【单次实测，2026-11-18】 |
| 时间码 | **不写**，事件挂在台词或动作上 | 写“00:07.200 睁眼”，12 种采样配置全都晚约 2 秒才睁眼；改成不写时间码、把睁眼挂在前一个动作之后，约 7.5 秒睁眼，早了约 1.5 秒【已验证】 |
| 一个镜头 | 只有一个主要任务；一个镜头只点一个主体 | 人多会逼模型自己切镜（WorkFisher 的经验，本片没有专门对照）【未验证】 |

**例外：紧接在打戏后面、画面必须接上的文戏。** 这种段要像武戏一样接上一段末尾的 22 帧（见 [continuation.md](continuation.md)），镜头的起止也可以写时间码，否则接缝后的第一个镜头会被模型自己拉长或缩短。本片战后的第一段对话就是这样出的。LoRA 仍然一个都不挂，节奏仍然写平静。【单次实测：一部片】

## 三、台词

1. **台词预算**：按每秒 4–5 个汉字算，再留出动作和音效的时间。10 秒的段台词加起来最多 40–50 字，动作多的段要更少。【已验证：一集 30 句台词，听写对上 29 句，且都在段内念完】
2. **点名说话人，倾听者闭嘴。** 每句台词前写 `名字 (S1), in <固定声线>, says <语气>,`；对面的人写“嘴唇闭着、静静听”。内心独白要明写“嘴唇不动”。
3. **一句台词不跨镜头。** 换人说话就切镜，一个镜头只给一个人说话。
4. **先走到位，再说话。** 边走边说会让人停下来对口型，所以写成“走四五步不说话，站定，然后才开口”。【单次实测】
5. **声线定稿后逐字沿用**，见 prompt-structure.md。
6. **广播、画外音**写成“从场地本身传来的声音”，画面里不出现播报员。
7. **同一个梗不跨段复读。** 一集里“三个月”“北美豆包”这类设定出现七八次，被评价“完全没必要”。设定交代一次就够，每句台词都要推进剧情。
8. **一件事只在一段里演。** 上一段末尾写了“两道流光朝擂台飞来”，下一段开头又演一遍，结果上一段停在两道光悬在半空，像卡住。下一段要演的事，上一段只给一个引子（抬头、一声尖啸）就停。
9. **事件要在画面上交代完**：人物落座、召唤物消失、对手离场，都要有一个镜头或一句话。

## 四、镜头怎么拍

- **不要正脸对着镜头摆拍。** 多用侧面、四分之三侧、过肩、低角度、俯拍；没有人看镜头。要给反应，就让镜头绕过去拍，或者硬切。【已验证】
- **对话拍法**：单人中近景，画面边缘留另一个人虚焦的肩膀；说话权换手就切。这是被明确表扬过的拍法。
- **镜头要动**：小幅手持晃动（“有真实感”）、缓慢环绕、推拉、摇臂升降、横移、移焦。每个镜头都写运镜，写法见 [camera.md](camera.md)；文戏的运镜以慢速、小幅度为主，急推和甩镜留给武戏。
- **开场钩子**：第一个镜头给人物胸口以上的近景，再拉开交代她在哪里、在做什么。不要开场就是大场景里一个小人。
- **脸部特写要写明所处环境**，否则模型可能把参考图原样贴出来闪一下。
- **“头肩填满画面”这类景别描述不可靠**，被画成过中景。景别用焦段加运镜写（例：85mm，从胸口以上推到双眼）。【单次实测，改法未验证】
- **每个镜头给一个环境锚点**（石板、柱子、看台）。写了“扬尘”的镜头，背景被画成了沙漠峡谷，不像原场景。
- **别加“淡淡尘雾”**。每个镜头都加，会让整段画面发灰发虚。【单次实测】

## 五、节奏：平静，不留“动作快”

武戏的风格段里有“快、爆发、干脆、越到结尾越快”这类句子，**复制文戏提示词时要删干净**，换成平静节奏的句子（例；这句是示意写法，没有单独对照过【未验证】）：

```text
The pace is calm and unhurried: people move at a natural walking pace, pause between lines, and the camera drifts slowly.
```

“平静”不是慢动作：仍然是真实速度，只是不抢拍、不拖拍。也不要写“慢动作”（作者要求全片动作按真实速度）。

## 六、一镜到底

想要不切镜，提示词里**所有** `Shot 2`、`hard cut`、`Hard cut to` 的字样都要删干净。它可能出现在好几处：`summary`、`retention_analysis` 的 `appears in [Shot 1], [Shot 2]`、`detailed_description` 的结构句和镜头正文。只改一处，模型仍会切。结构句换成 `The whole video is one continuous shot with no cuts.`，并写清镜头从哪个机位出发、怎么动、停在哪个构图。【单次实测】

反过来也成立：写了 2.2 秒处硬切，模型有时不切，变成连贯运镜；写成不切的一整圈环绕，模型也曾在 0.5 秒后自己切了一刀。验片时按成片判断能不能接受，不要假设写了就切、写了不切就不切。

## 七、站位与连续性

每段都是独立生成的，模型不记得上一段。**下面这些每段都要重写**：

- 伤、嘴角的血、撕破的衣服：伤只累积不消失，后面每一段都写，每次变化要有来由；
- 持械的手：左手还是右手、正手还是反手，写进角色描述，每段重写。曾经有段落里持剑的手变成左手或反手；
- 脚步声：高跟鞋、厚底鞋的声音写进 `overall_soundscape`，下一段不写就没了；
- 人物间距写成具体数字（例：“十步、约八米”），并写明本段谁都不挪步；
- 座位、方位：全片定一张方位表，每段的站位只用表里的固定说法（见 [../../drama-preproduction/references/state-table.md](../../drama-preproduction/references/state-table.md)）。

镜头位置会遮住信息：近侧机位拍不到远侧的东西。右手的剑在身体背面、左脸的伤在背光那一侧，镜头就看不到。伤写在朝向镜头的一侧；持械手要么写明“在远侧、剑柄从身后露出”，要么换一个能看到它的机位。

## 八、段与段怎么接

文戏段停在**完整节点**：对峙、说完一句话、全场欢呼。下一段直接硬切，站位对上上一段结尾即可，不需要接帧。详见 [continuation.md](continuation.md)。

文戏接武戏时站位尤其容易错：文戏结尾一个人已经走到另一个人面前，下一段开头两人却在场地两头。写下一段前，先把上一段结尾的站位和距离抄进状态表。

## 九、写一个镜头的样子

例（只示意结构，台词换成你自己的）：

```text
[Shot 1] A medium-wide side tracking shot from the near side at hip height, <Subject 1> small and soft at the far left edge of the frame.
<Subject 2> walks across the floor from screen right toward screen left, her body in profile, the longsword hanging in her right hand with the blade trailing behind her.
She says nothing for four or five steps, her head tilted, her lips curled; she stops about ten strides from Subject 1, and only then
GPT (S2), in a mature young female voice, smooth and elegant, arrogant and slightly drawling, says mockingly, <d>[Chinese]台词写在这里</d>
The camera tracks alongside her at walking speed, slightly handheld, and stops when she stops.
[Shot 2] Hard cut to a slowly arcing close-up of Gemini in three-quarter profile from her right side, standing perfectly still, golden light on one side of her face.
Gemini (S1), in a young female voice around twenty, cool and clear mid-pitch, calm and measured pace, says coldly, <d>[Chinese]台词写在这里</d>
Her right eye is blue and her left eye is gold, exactly as in her reference picture. The camera keeps arcing slowly around her.
```

要点：没有时间码；事件挂在“停下之后才开口”上；每个镜头写起始机位和运镜；眼睛颜色在特写里再强调一遍。

## 十、排队与耗时

文戏段之间用硬切，站位由状态表固定、不依赖上一段成片，所以可以排队批量出，通宵出完再统一验片（见 [qc.md](qc.md)）。例外是文戏接武戏的交界：武戏的开头要照文戏**实际**的结尾状态写，所以先验完这一段文戏，再写接在它后面的武戏。耗时：每秒成片约 1.5–2 分钟（RTX 5060 Ti 16 GB，1536×864，24 fps），10 秒的段约 15–21 分钟，12 秒约 18–24 分钟（后者按比例推算）。

# H3 提示词字段骨架

什么时候读：第一次给 H3 写参考生视频（Ref2VA）提示词时，或者某段出来的东西和你写的对不上、想先检查骨架有没有写错时。文戏和武戏共用这套骨架，差别只在 `detailed_description` 里怎么写镜头，分别见 [dialogue.md](dialogue.md) 和 [fight.md](fight.md)。

可信度标注：【已验证】多次出片确认；【单次实测】只在一两段上看到；【未验证】推断或没对照过。

## 一、六个字段

沿用 MiniMax H3 官方提示词指南和官方扩写器的 Ref2VA 格式。参考图按出现顺序编号，`<Subject N>` 对应 `<Picture N>`。

| 字段 | 写什么 | 注意 |
|---|---|---|
| `subject_definitions` | 每个参考图一段：人物写与参考图一致的身份要点，加上固定的动作设定（持剑方式、手里有没有武器）；场景写布局和地标 | 不要写成长篇小传。参考图里看得见的东西，只写容易漂的部分，见第三节 |
| `summary` | 一句话：几个镜头、发生什么、停在哪里 | 镜头数要和正文一致；想一镜到底就不能出现 Shot 2 或 hard cut（见 dialogue.md） |
| `retention_analysis` | 每个主体出现在哪些镜头，写 `fully_preserved` | 这里也有镜头编号（`appears in [Shot 1], [Shot 2]`），改镜头数时要同步改 |
| `detailed_description` | 正文，顺序见第二节 | 全文最长的一块 |
| `overall_soundscape` | 环境声和动作音效；硬切处写一句“不加呼啸声或转场音”；连续性用的声音（高跟鞋脚步声）也写在这里 | 台词不写在这里，写在镜头里 |
| `non_diegetic_music` | 一律 `N/A` | 每段都让模型配乐，几十段拼起来会一会儿一个调；配乐在后期统一加（见 drama-postproduction） |

## 二、detailed_description 的顺序

1. **风格段**：画风、画质、光线、动作速度、物理、画面方向不翻转、“只有上面定义过的主体出现在前景”、“画面上没有文字”。全片逐字相同，每段复制。
2. **力量设定**（可选）：一人一句，例“Gemini 的力量是蓝紫星光”。
3. **本段规则**：武戏放速度与节奏句、固定地理、命中与尺度规则（见 fight.md）；文戏放一两句这场戏的情绪和人物状态。
4. **结构句**：`The video is 3 shots joined by hard cuts: every cut is a straight cut, with no dissolve, no fade and no transition effect.`；一镜到底写 `The whole video is one continuous shot with no cuts.`；武戏再加 `The video consists of exactly the shots written below, in that order.`
5. **`Positions:` 站位**：不算镜头。写谁站在哪、朝哪、手里拿什么、伤成什么样（来自全片状态表，见 [../../drama-preproduction/references/state-table.md](../../drama-preproduction/references/state-table.md)）。
6. **`[Shot 1]` `[Shot 2]` …**：镜头正文。

骨架（英文出片，括号里是给你的说明，不要写进提示词）：

```text
subject_definitions:
<Subject 1> is <人物，与 <Picture 1> 一致的身份要点 + 容易漂的细节 + 固定动作设定>.
<Subject 2> is <场景，布局和地标>.

summary:
[reference generation] <N shots: 发生什么，停在哪里>.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - the face, hairstyle, outfit, accessories, and signature color are retained.

detailed_description:
<风格段> <力量设定> <本段规则> <结构句>
Positions: <站位，不算镜头>
[Shot 1] <起始机位与景别。发生了什么。台词。运镜>
[Shot 2] Hard cut to <...>

overall_soundscape:
<环境声，动作音效，连续性声音>. No whoosh or transition sound is added at the hard cuts.

non_diegetic_music:
N/A
```

## 三、写法规则

1. **写了的东西都会被画出来，包括设定说明。** 曾经在站位里写“地面中央一个焦坑”，结果每一段都画出一个大坑。不想出现在画面里的东西，一个字也别写。【已验证】
2. **没给参考图的角色，不要写进站位。** 站位里写了“前排三个人提着灯笼”，可这几段没挂她们的参考图，模型就在地面边上画了三个穿黑衣、坐着的陌生人和一盏灯笼。改成“看台在围墙外远处、虚化；地面上除了两人没有任何人”。【单次实测，同一问题出现在 4 段】
3. **容易漂的细节要在角色描述里写死，而且写成正面描述。** 提示词里一句“瞳孔里的星亮了一下”，就把一蓝一金的异色瞳盖成了两只蓝眼；特写里露肩上衣漂成了高领；光剑状的武器要写“实心钢剑身，真金属，每个镜头长度和形状一样”。【单次实测】
4. **全文用名字，不用代词。** 方位用画面坐标：画面左、右、中央、前景、远处。持械手也用画面坐标加左右手写清楚。【已验证】
5. **声线定稿后逐字沿用。** 每个说话人一句固定的声线描述（例：`a young female voice around twenty, cool and clear mid-pitch, calm and measured pace`），每段原样复制，否则同一个人每段声音不一样。【已验证】
6. **台词格式**：`<名字> (S1), in <声线描述>, says <语气>, <d>[Chinese]台词</d>`。点名说话人；倾听者要写明“不说话、嘴唇闭着”；一句台词不跨镜头。台词保留中文，其余英文。【已验证】
7. **排除项尽量改写成正面描述。** 这个流程是 CFG 1，没有负面提示词，“不要红光”之类的写法可能反而把红光带进画面。需要排除易混淆物体时，写“是 A，不是 B”的对照句（例：`light, not flesh and not a thin beam`）；速度和停顿类的否定词一律不用（见 fight.md）。【单次实测；机理是推断】
8. **英文出片，中文对照给人审。** 用同一份脚本同时生成英文提示词和逐句中文翻译（`scripts/build_shots.py`），两份内容一一对应；审稿看中文，渲染用英文。
9. **长度**：官方指南建议参考生视频 350–500 词；本片实际出片的提示词长得多，1300–2200 词（含角色定义和风格段）。长短对画面的影响没有对照过。【未验证】
10. **每个被写进去的镜头都要有用。** 写了的镜头模型会照做，不要用“通用规则”描述没有出现的画面，见 fight.md 的“通用规则会变成镜头”。
11. **同一段改提示词时种子不动**，只有在提示词不变、想换一个结果（抽卡）时才换种子。这样提示词改一处，画面的变化才能归因到这一处。不同的段可以用不同的种子（本片各段的种子并不相同）。

## 四、参考图

- 人物：定妆图，左边约 40% 是大的头肩特写，右边是正、侧、背三视图。角色描述里写明“脸照左边特写，服装照右边全身”。做法见 [../../drama-preproduction/references/ref-images.md](../../drama-preproduction/references/ref-images.md)。
- 场景：一张完整场景图；场景有受损阶段时，每个阶段一张（见 fight.md 的“破坏只做小范围”）。
- 召唤物：单独一张，见 [summons.md](summons.md)。
- **武戏不挂关键帧**：参考图只给人物和场景，机位全靠文字写（见 [camera.md](camera.md)）。文戏同样只给人物和场景。
- 参考图以这一段里真正出场的人和物为准：出场的一定要挂，不出场的人不要写进站位（原因见第三节第 2 条）。

## 五、出片前机械检查

`scripts/check_script.py` 对 shots.json 做这些检查，每段出片前跑一遍：

- 时长不超过 12 秒；武戏不超过 10 秒；接续段新内容不超过 9.9 秒、含接续帧不超过 260 帧（见 continuation.md）；
- 没有残留的 `{占位符}`，`<Subject N>` 的编号没超过参考图张数；
- 站位里出现的人物、召唤物都挂了参考图；
- 武戏每个镜头都有时间码；武戏里除了招牌大招，没有别的台词；
- 没有禁用词（例：`no slow motion`）；
- 声明了首帧或接续的段，提示词里写了“从锚定画面 / 上一段中途开始”和“接续上一画面”。

左手握剑、反手握剑、正对镜头、没有来由的着火、座位左右这类**你自己的片子**踩过的坑，写进规则 yaml（`--rules`，示例在 `examples/gemini-revenge/data/rules.example.yaml`），比通用规则更有用。数据文件的写法（`build_shots.py` 的输入）见 `examples/gemini-revenge/data/segments.example.yaml`。

## 六、配置与耗时

采样配置（专属二采）、LoRA 链、分辨率、步数不在这个 skill 里讲，见 [../../h3-video/references/recipes.md](../../h3-video/references/recipes.md)。

实测耗时（RTX 5060 Ti 16 GB，1536×864，24 fps）：文戏每秒成片约 1.5–2 分钟，武戏约 2.4–2.7 分钟。帧数要取 17k+5（例：226、243、260），队列会自动向上取整。

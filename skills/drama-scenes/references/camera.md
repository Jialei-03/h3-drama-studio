# 运镜写法

什么时候读：给每个镜头写机位和运镜时。文戏和武戏都用；武戏不用关键帧，镜头构图全靠这里的两行字，所以更要认真写。

可信度标注：【已验证】多次出片确认；【单次实测】只在一两段上看到；【未验证】推断或没对照过。

## 一、每个镜头写两样东西

| 行 | 写什么 | 为什么 |
|---|---|---|
| **起始机位**（本片写成 `Framing:`） | 焦段、高度、在谁的哪一侧、景别 | 没有关键帧，第一帧的构图只由这一句决定。机位没写清，场景细节会被模型自己编：早期只给一张俯视场景图时，低机位和反打镜头里石碑被画成废墟或记分塔【单次实测】 |
| **运镜**（本片写成 `Camera:`） | 类型 + 幅度 + 速度 + 动机 + 落幅 | H3 官方要求每个镜头都写运镜；镜头不动也要写 `Static Shot`，不写模型就自己乱猜【已验证】 |

先写起始机位，再写运镜。两行用不同的词头只是为了你自己好读，词头本身有没有影响没有对照过【未验证】。

## 二、词表（H3 官方）

- 类型：Push In / Pull Out、Zoom In / Out、Pan、Truck、Tilt、Pedestal、Arc Shot、Tracking Shot、Static Shot、Shake Slightly / Strongly、POV、Roll。本片还用过 Whip Pan（甩镜）、Crane Up、Handheld。
- 幅度：with small / large amplitude。
- 速度：at slow / fast speed。
- 写成自然的英文句子，不要堆标签。每个镜头只放一个主要动作。

## 三、起始机位怎么写

- **焦段**：14 / 18 / 24 / 35 / 50 / 85 / 100 / 200 mm。焦段同时是一种感受：超广角让人变成“一粒火点”，长焦把距离压扁、“整群被压成一道逼近的锋线”。
- **高度**：贴地超低、膝盖、胸口、眼睛、无人机高空。
- **在谁的哪一侧**：“低机位，在 Gemini 左肩后，她的后背和头发在画面左侧前景”；两人对打时镜头始终在两人连线的同一侧。
- **景别**：全景、中景、近景、特写，必要时加“胸口以上”。景别描述不够可靠（“头肩填满画面”被画成过中景），要用焦段加运镜配合。
- **荷兰角**倾斜 25–45°：留给失控、被压制的时刻，别滥用。
- 不要正脸对着镜头：多用侧面、四分之三侧、过肩、低角度、俯拍。【已验证】

例（起始机位）：

```text
Framing: a 35mm lens low behind Gemini's left shoulder, tilted up, her back and hair in the left foreground, GPT hovering in mid-air high above the pillar tops at screen right.
Framing: an 18mm ultra-wide lens almost on the ground directly behind Gemini, tilted up, her back centered low in the frame, the sky filling the upper half.
```

## 四、运镜怎么写：要有动机

1. **镜头因为动作而动。** 被冲击波推开、被拖着跑、被震得一跳、被碎石遮住、跟着被打飞的东西甩过去；它追不上，只捕捉到残影。没有动机的运动显得飘。
2. **推开镜头的必须是对手的攻势。** 写成“镜头被主角逼退”，主角就会正对镜头出手。【单次实测】
3. **用数字写距离变化**：“从两公里推到八百米”“400 米 → 180 米 → 80 米”。
4. **冲击用三件套**：震一下（`Shake Strongly`）加急推，或者甩镜，或者被冲击推后。每段的收尾冲击至少用一种。
5. **急推和实推不一样**：急推（`Zoom In` 的 crash zoom）是突然强调，实推（`Push In`）是持续施压。甩镜要么甩到真快，要么不甩；甩镜停住后接急推到脸或武器上，等于再打一拳。
6. **跟东西飞一趟**：镜头跟着刀光、被打飞的人飞到落点，再切。
7. **巨物用超远视角，人对人用侧面跟拍和过肩。** 人缩成一粒火点，巨物才显得巨大；侧面跟拍视差最强，速度感最好。
8. **大全景也要动**：用急推、被冲击推开。电影常识说大全景可以静止让人看清招式，但本片发现对轰变慢后，把大全景从“静止镜头、锁定不动”改成急推和被冲击推开。【单次实测，2026-11-20】
9. **镜头不该动时写死“镜头不动”。** 例：上一段是大远景拉远，下一段就从同一机位直接让人飞出去，不要先推近（曾经开头变成推近再飞出去，接缝对不上）。
10. **巨物冲向镜头**：这一镜里只有巨物，写明 `only the dragon is in this shot`；镜头可以往后甩，但巨物要快得多（“镜头退得比不上巨物冲得快”）；吞没镜头后闪白。前一镜写明巨物停在高处，不要让它从人身上穿过去。【已验证】

## 五、一段之内：切还是不切

- **一段里镜头的运镜不重复**，例：静止大全景 → 侧面跟拍 → 急推。
- **切镜要带来新信息。** 只是景别或角度变了，用运镜完成，不要切。
- **不切就写清三件事**：镜头从哪个机位出发、怎么动、停在哪个构图。例：一个 6.5 秒不切的手持长环绕，连续打击，被评价很好。【单次实测】
- 每个镜头写明是在几秒硬切，还是不切。写了硬切，模型也可能不切；写了不切，也可能自己切（见 dialogue.md 第六节）。验片时按成片判断。
- 接续段的第一个镜头，起始机位就是上一段结尾的机位，见 [continuation.md](continuation.md)。

## 六、文戏的运镜

文戏用慢速、小幅度（下面几条都是被明确表扬过的写法；快慢没有单独对照过）：

- 小幅手持晃动（被评价“有真实感”）；
- 缓慢环绕、缓推、摇臂升降、横移、移焦；
- 对话：单人中近景，画面边缘留另一个人虚焦的肩膀，换人说话就切；
- 速度和幅度写 `slow`、`small amplitude`；不用急推、甩镜、剧烈震动。

例（运镜）：

```text
The camera tracks alongside her at walking speed, slightly handheld, and stops when she stops.
The camera keeps arcing slowly around her.
```

## 七、武戏运镜的例子

例（本片用过的几种，机位和动机都写在句子里）：

```text
Camera: Zoom In at fast speed, a crash zoom onto the collision point the instant the attacks meet, then Shake Strongly as the explosion goes off, and the shockwave blows the camera backward, pulling out with large amplitude at fast speed.

Camera: Arc Shot with large amplitude at fast speed: one continuous handheld orbit that keeps circling GPT all the way round without stopping or cutting, the afterimages streaking through the frame between the lens and her, the camera jolting at every hit.

Camera: Static at first, then whipping backward and jerking sideways, Shake Strongly, as the dragon charges far faster than the camera can retreat and its jaws swallow the lens.

Camera: Push In with large amplitude at fast speed like an FPV drone racing through the clouds toward the fight, from two kilometres to eight hundred metres, cloud wisps streaking past the lens.
```

## 八、不要这样写

| 写法 | 结果 | 改法 |
|---|---|---|
| 起幅写进关键帧，让关键帧当运镜的起点 | 镜头参考图让运镜不自然（见 failure-cases.md） | 不用关键帧，起始机位写成文字 |
| “掩埋转黑”：烟尘把镜头埋住，画面变暗，再被光割开（WorkFisher 的手法） | 一段里出现过黑帧，删掉这句后没再出现，二者是否有因果没验证【单次观察】 | 改成“尘土扑过镜头”，不写“画面变暗” |
| 急推到撞击点再闪白、甩回大全景 | 一片雾蒙蒙的空画面 | 第一帧就全速；中间切一个人物近景 |
| 镜头被主角“逼退” | 主角正对镜头出手 | 镜头被冲击波或对手的攻势推开 |

## 九、来源

- MiniMax H3 官方提示词指南：运镜“类型 + 幅度 + 速度”的写法。
- WorkFisher 的武戏导演教程：先写机位在主角哪一侧，再写感受；把镜头当成被卷进打斗的人。
- 吃猪侠233 的打戏模板：每个镜头写焦段、机位高度、荷兰角、时间码。
- 电影摄影常识：[StudioBinder 的甩镜指南](https://www.studiobinder.com/camera-shots/camera-movements/whip-pan-shot/)、[Whip zoom（维基百科）](https://en.wikipedia.org/wiki/Whip_zoom)。

这里只写学到了什么，原工作流和提示词原文不在本仓库里；想看原版请去他们各自的发布渠道。

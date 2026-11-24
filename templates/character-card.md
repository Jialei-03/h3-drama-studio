# 角色卡

用在环节 1（故事与人设），每个有脸的角色一张；召唤物也可以用，只填适用的行。**写完不再改**：改一个字，已经出好的段就可能要重出。
写法和理由见 `skills/drama-preproduction/references/story.md` 第 4 节、`ref-images.md` 第 4 节。花括号 `{}` 换成你的内容，"例："是作者片子的写法。

## 角色：{名字}

| 项 | 填写 | 提示 |
|---|---|---|
| 名字、一句话 | {身份 + 一个性格词} | 台词和表演都从这里长出来 |
| 弧线 | {开头的状态 → 结尾的状态} | 每段表演要能说出"她这时处在弧线的哪里" |
| 标志色和光效 | {一种颜色 + 一种光效。例：蓝紫星光} | 特效一眼分谁的；对打双方的特效写成同一量级 |
| 力量设定（一句英文） | {例：Gemini's power is blue-to-violet starlight.} | 放进 `detailed_description` 的力量设定 |
| 体型 | {和别人的身高关系；与场地的尺度关系。例：普通人的身高，比对手矮半个头} | 人物永远是人的大小，不要写 colossal、towering |

## 外观锁定项（写成能直接放进 `subject_definitions` 的英文）

```text
<Subject {N}> is the young {国籍/种族} actress playing {名字} in <Picture {N}> (her face exactly as in the large close-up on the left of that picture, her costume as in the three full-body views on the right), about {年龄}, with {表情基调}; {发型发色}; {头饰/配饰}; {眼色，左右眼分开写}; {服装关键件，逐件写}; {道具或持械，见下}.
```

| 项 | 填写 |
|---|---|
| 发型发色 | {一旦定稿不再改} |
| 眼色 | {例：右眼蓝、左眼金，瞳孔里没有星星、不发光} |
| 服装关键件 | {逐件，含"没有领子"这类否定变成的正面描述} |
| 配饰 | {} |

## 易漂移细节（每一条都写成正面描述，并在每段的角色描述里重复）

| 容易被画错的点 | 写死的说法 |
|---|---|
| {例：眼色左右} | {例：her right eye blue and her left eye gold, in every close-up, with no stars or glow in them} |
| {例：上衣领口} | {例：an off-shoulder top that leaves her shoulders bare, with no collar and no high neck} |
| {例：武器是不是光束} | {例：a solid polished steel blade, real metal, never a beam of light, the same shape and length in every shot} |
| {} | {} |

## 持械、招式

| 项 | 填写 |
|---|---|
| 持械的手、握法 | {例：always in her right hand with a normal forward grip, the blade extending from the thumb side of her fist, never a reverse grip and never in her left hand}。每段重写 |
| 拖剑时剑在哪 | {例：剑在身后，剑尖在脚跟后面} |
| 空手 | {例：fights bare-handed and never holds a sword or any weapon} |
| 招牌大招（一个，英文名） | {例：Supernova!}。动作中途一口气喊出，不能站定了再念 |

## 声线（一句英文，定稿后每段逐字复制）

```text
{例：a young female voice around twenty, cool and clear mid-pitch, calm and measured pace}
```

- 台词格式：`{名字} (S{n}), in {上面这句声线}, says {语气}, <d>[Chinese]台词</d>`
- 和同场其他角色的声线要拉开差距（年龄感、音色、语速各不同），否则两个人的声音会串。

## 参考图

| 项 | 填写 |
|---|---|
| 定妆图文件名和版本 | {例：char_xxx_v3.png。左边约 40% 大头肩特写，右边正、侧、背三视图，16:9} |
| 定稿日期 / 是否已冻结 | {} |
| 在视频提示词里的分工句 | face from the large close-up on the left, costume from the full-body views on the right |
| 出场段 | {段号列表} |

## 检查

- [ ] 外观锁定项能直接复制进提示词
- [ ] 易漂移细节至少写了 3 条，且都是正面描述
- [ ] 声线一句话，和同场其他角色听得出区别
- [ ] 持械的手写明了左右和握法
- [ ] 定妆图放大到原尺寸看过，用户确认

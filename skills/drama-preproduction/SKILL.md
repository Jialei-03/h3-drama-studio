---
name: drama-preproduction
description: AI 短剧开拍前的全部准备：写故事节拍和角色设定，做人物、场景、召唤物的参考图，把故事拆成段和镜头，建立全片状态表保证前后一致，以及出稿前的三遍审稿和机械检查。在写或改剧本、设计角色、出定妆图或场景图、拆分镜、检查前后是否一致时使用。Pre-production for AI short drama: story beats, character and scene reference images, shot breakdown, continuity state table, script review.
---

# 短剧前期：故事、定妆、剧本、状态表、审稿

开拍前的五步。每一步产出一份东西，**用户确认后再进下一步**：出片一段要十几分钟到半小时，前期改一句话几乎不花钱。

| 步骤 | 做什么 | 产出 | 用户确认什么 | 读 |
|---|---|---|---|---|
| 1 故事 | 一句话故事、节拍表、角色卡、台词规矩 | 节拍表 + 每个角色一张角色卡 | 故事和人设 | `references/story.md` |
| 2 定妆 | 人物定妆图、场景图、召唤物图、受损阶段场景图 | 每项一张定稿参考图 | 图像（脸像不像、画风对不对） | `references/ref-images.md` |
| 3 剧本 | 拆段、拆镜、台词预算、中英提示词、逐句中文翻译 | 段落清单 + 每段提示词 | 段落清单、中文翻译 | `references/script.md` |
| 4 状态表 | 方位、座位、光线、尺度、场地和人物的各阶段状态、持械 | 全片状态表 + 衔接表 | 表里的每一行 | `references/state-table.md` |
| 5 审稿 | 作家、漫画家、动画导演三遍审 + 机械检查 | 改完的提示词 | 中文全剧本 | `references/review.md` |

步骤 3 和 4 要来回做：先建状态表的"全片不变"行（方位、座位、尺度、持械），再写每段，写的时候随时往表里加阶段。

## 现在遇到什么，读哪个文件

| 情况 | 读 |
|---|---|
| 只有一个点子，不知道怎么变成一集 | `story.md` 第 1、2 节 |
| 打戏被嫌单调、没看头 | `story.md` 第 3 节 |
| 台词少、复读、角色说话都一个样 | `story.md` 第 5 节 |
| 要给新角色出定妆图 | `ref-images.md` 第 4 节 |
| 视频里背景自己长出来了 | `ref-images.md` 第 5 节 |
| 场地被打坏后前后段不一致 | `ref-images.md` 第 7 节、`state-table.md` 第 3 节 |
| 不知道一段该多长、几个镜头 | `script.md` 第 2、3 节 |
| 台词说不完、人物站着对口型 | `script.md` 第 4 节 |
| 一件事被演了两遍 | `script.md` 第 5 节 |
| 左右反了、伤口消失、人忽大忽小 | `state-table.md` |
| 出片前不知道怎么审稿 | `review.md` |
| 要写出片用的提示词字段、运镜、衔接做法 | 交给 `drama-scenes` |

## 必须遵守的规则

1. **先故事，后提示词。** 看片时被挑出来的是"没看头""台词少""空镜多"，没有一条是工作流。`story.md`
2. **每一步用户确认后再进下一步。** 参考图换版会让已出好的段全部重出。`ref-images.md`
3. **第一个镜头先给人物近景，再拉开交代环境。** 大场景里一个小人，观众看不清她是谁。`story.md`
4. **台词多、句子长；同一个梗不跨段复读；打斗中不说话。** 第一版"北美豆包"出现七八次，全部删掉。`story.md`
5. **打戏是亮点，段数要多于文戏。** 第一版打戏被嫌"只是挥舞一下手臂或剑"。`story.md`
6. **人物定妆图：左边约 40% 大头肩特写，右边正侧背三个全身视图，16:9。** 特写让中远景里的脸不糊。`ref-images.md`
7. **画风写成"真人实拍定妆照 / 好莱坞真人大片截帧"；排除项写成正面描述。** 写"不要红光"反而出红光。`ref-images.md`
8. **每个场景、召唤物、受损阶段各一张参考图，每段都挂。** 没挂场景图，背景变成别的地方；柱子损坏靠文字保不住。`ref-images.md`
9. **文戏最长 12 秒、2–5 个镜头、不写时间码；武戏 5–10 秒、镜头不设上限、每镜每拍写时间码。** 文戏写"00:07 睁眼"会晚约 2 秒；武戏不写时间码会被拉慢。`script.md`
10. **台词预算每秒 4–5 个汉字；说话人换了就切镜；一句不跨镜头。** 超预算说不完，边走边说会停下对口型。`script.md`
11. **一件事只在一段里演；事件要在画面上交代完。** 上一段演"光飞来"，下一段又演一遍，上一段就停在半空。`script.md`
12. **提示词用英文出片，每段附逐句中文翻译给用户过目。** 把关的人要用母语核对每一句会被画成什么。`script.md`
13. **站位说法只从状态表里取，一字不改；伤和破坏只累积、不消失。** `state-table.md`
14. **没挂参考图的人不要写进站位。** 否则模型在地面边上画几个陌生人。`state-table.md`
15. **出片前三遍审稿加机械检查，全过才排队。** 出一段要十几分钟，审稿只要几分钟；三个身份查出的问题类别不同。`review.md`

## 脚本

| 脚本 | 用在 |
|---|---|
| `scripts/relay_img.py` | 带参考图出一张图（走 `config.yaml` 的 `image_api`）：`relay_img.py 输出.png 提示词.txt [参考图…]` |
| `scripts/kf_batch.py` | 按 yaml 清单批量并发出图：`kf_batch.py 清单.yaml --tag r1` |
| `scripts/build_shots.py` | 分段提示词数据（yaml）→ `shots.json`（给队列用）+ 逐句中文翻译 `prompts_zh.md`：`build_shots.py segments.yaml` |
| `scripts/make_full_script.py` | 从同一份数据生成给人看的中文全剧本：`make_full_script.py segments.yaml` |
| `scripts/check_script.py` | 出稿前机械检查：`check_script.py shots.json --rules rules.yaml --data segments.yaml` |

数据文件和规则文件的带注释示例在 `examples/gemini-revenge/data/`。这些脚本都有 `--dry-run` 或只读输出，**未在干净环境端到端验证**（出图脚本没有对真实服务调用过）。

出图用到的变量：`image_api.base_url_env`、`image_api.key_env`、`image_api.model`（见仓库的 `config.example.yaml`）。密钥只放在环境变量里。

## references

| 文件 | 内容 |
|---|---|
| [story.md](references/story.md) | 篇幅与范围、节拍表、打戏节拍、角色卡、台词风格 |
| [ref-images.md](references/ref-images.md) | 人物、场景、召唤物、受损阶段图；出图路线、画风写法、验收清单 |
| [script.md](references/script.md) | 段长、镜头数、台词预算、衔接、中英提示词、段落清单模板 |
| [state-table.md](references/state-table.md) | 状态表规则；状态表和衔接表的可填模板 |
| [review.md](references/review.md) | 三种身份审稿、机械检查项、常见通病 |

## 上下游

- 上游：`ai-drama`（总路线）、`local-ai-workstation`（出图和出片的机器要先通）。
- 下游：`drama-scenes`（拿着本 skill 的段落清单、提示词和状态表去出片）、`h3-video`（出片配方和队列）。

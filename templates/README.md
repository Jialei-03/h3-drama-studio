# templates

可以直接复制到你的项目目录里填写的模板。每个文件开头有"用在哪个环节"和填写说明；`{花括号}` 是要你换掉的内容，"例："后面是作者片子的写法，填完删掉。
环节编号是 `skills/ai-drama/SKILL.md` 里的 12 个环节（0 部署 … 11 发布）。

## 按环节

| 环节 | 模板 | 用来做什么 | 对应的 skill / reference |
|---|---|---|---|
| 1 故事与人设 | [story-beats.md](story-beats.md) | 故事节拍表 + 打戏升级阶梯 + 台词规矩；先写它，再拆段 | `drama-preproduction`：`story.md` |
| 1 故事与人设 | [character-card.md](character-card.md) | 每个角色一张卡：外观锁定项、易漂移细节、持械、声线 | `drama-preproduction`：`story.md` 第 4 节、`ref-images.md` |
| 3 剧本与状态表 | [state-table.md](state-table.md) | 全片状态表（方位、座位、光线、尺度、场地和人物状态、持械）+ 段间衔接表 | `drama-preproduction`：`state-table.md` |
| 5 文戏出片 | [prompt-dialogue.md](prompt-dialogue.md) | 文戏提示词骨架（英文 + 中文注释），不写时间码、平静节奏 | `drama-scenes`：`prompt-structure.md`、`dialogue.md`、`camera.md` |
| 6 武戏出片 | [prompt-fight.md](prompt-fight.md) | 武戏提示词骨架：时间码、起始机位 + 运镜、命中四样结果、接续、结尾收在冲击上 | `drama-scenes`：`prompt-structure.md`、`fight.md`、`continuation.md` |
| 7 验片与返工 | [take-log.md](take-log.md) | take 记录表（段、take、种子、配置、结论）+ 验片清单 + 每段结尾状态 | `drama-scenes`：`qc.md` |
| 8 批量与通宵 | [morning-checklist.md](morning-checklist.md) | 通宵出片后的早上检查清单：队列、失败、联系表、听写、接缝、回收显卡 | `h3-video`：`queue.md` |
| 9 粗剪与改稿 | [revision-list.md](revision-list.md) | 改稿清单：全局规则、逐段、需要重出的段（链式衔接）和重出估时 | `drama-postproduction`：`rough-cut.md` |
| 9 粗剪与改稿 | [cut-plan.md](cut-plan.md) | 剪辑方案：时间点、打算怎么改、原因、对后面的影响、是否批准；时间平移表 | `drama-postproduction`：`rough-cut.md` 第 4、6 节 |
| 11 发布 | [publish-checklist.md](publish-checklist.md) | 发布前检查：交付文件夹、成片规格、封面、文案、AI 声明和配乐版权 | `drama-publish`：`export.md`、`covers.md`、`copywriting.md` |

## 其他

| 文件 | 用来做什么 |
|---|---|

项目专属的数据文件（分段提示词数据、检查规则）的带注释示例不在这里，在 [../examples/gemini-revenge/data/](../examples/gemini-revenge/data/)：`segments.example.yaml`（`scripts/build_shots.py` 的输入）和 `rules.example.yaml`（`scripts/check_script.py` 的规则）。

## 怎么配合着用

```
story-beats + character-card   →   state-table   →   prompt-dialogue / prompt-fight
                                                          ↓
                       take-log ←── morning-checklist ←── 出片（队列）
                          ↓
              revision-list  →  cut-plan  →  publish-checklist
```

- **前期（不占显卡）把表填满**：节拍表和角色卡用户确认之后再建状态表；状态表定稿之后再写提示词。改一句话几乎免费，出一段要十几分钟到半小时。
- **每段提示词的站位只复制状态表里的句子**，每段验完把实际的结尾状态抄回衔接表，下一段从那里写起。
- **改稿先给方案**：`revision-list.md` 整理意见，`cut-plan.md` 列要剪哪里，用户批准后才动手。

# MiniMax H3 漫剧制作 Skill

面向 16:9 横屏漫剧项目的 MiniMax H3 独立制作工作流，覆盖故事与剧本、视觉资产、导演分镜、H3 提示词编译、项目校验、生成状态管理、剪辑和交付。

本 Skill 只管理 MiniMax H3 的模式、提示词字段、说话人和对白标记及调用边界。Seedance 2.0/2.5 的语法、模式、额度和参数不适用于本 Skill。官方模型生成时长为4–15秒；本项目提示词默认中文，字段名和固定语法保持官方格式。Ref2VA最多9图、3视频、3音频，混合输入最多12个。服务能力会随 provider 和接口变化，实际提交前须核验当前文档与 schema。

完整单集目标为90–180秒，由多个4–15秒的H3生成段连续承载。剧本冻结前按证据审查因果、人物、关系、道具和可视听性；诊断与改写分开，改写后复查受影响的前后场次。

## 安装与调用

将本仓库目录复制到 Codex skills 目录，并保留仓库内的目录结构：

```text
~/.codex/skills/minimax-h3-manju/
```

Windows 默认目录通常为 `%USERPROFILE%\.codex\skills\minimax-h3-manju`。也可按自己的 `CODEX_HOME` 配置放置。随后在 Codex 中调用 `$minimax-h3-manju`。

用户明确选择 MiniMax H3 后，Skill 才编译 H3 提示词。若用户只要求制作漫剧但没有选模型，先询问流程。所有画面按 16:9 规划；生成请求还须有当前能力证据、真实素材映射、明确 job 范围和费用上限。

测试和试跑统一使用外部目录 `E:\Test-data-Skill`。全流程测试、测试视频、H3/资产提示词测试、资产图生成测试及其输入副本、输出、抽帧、日志和报告都放在 `E:\Test-data-Skill\<project_id>\`，项目目录不创建这些内容。批次目录格式为 `YYYYMMDD-HHmmss_<kind>_<slug>`，详细子目录和路径规则见 `references/project-contract.md`。

## 工作流

1. 确认项目范围、主/次题材、关系类型、交付物和预算边界；为每个主类型建立 `genre_card_id`，记录观众承诺、故事循环、状态账本、资产家族和连续性锁定。
2. 按输入完成原创故事、小说改编、剧本诊断或局部修订，并冻结台词。
3. 建立视觉基准，制作人物、场景和道具资产提示词；角色默认使用一张四视图板，脸部设计放在同一张板的胸像区域。
4. 为每个固定发声角色建立稳定音色档案，再为每个4–15秒生成 job 完成覆盖全时长的导演谱和段卡，锁定剧情职责、首尾状态、出场顺序、人物与场景的画面比例、景别和视点切换、双重站位、微表情、对白演绎、声音和运镜触发/停止点；逐镜列出实际绑定的已审核角色、场景和道具资产。
5. 导演谱通过后，按实际输入选择 H3 模式并编译。导演谱使用 schema 1.2，逐镜记录人物画面占比、景别、视点和切镜理由。故事板仅在文字镜头表无法核清剧情顺序且预演有明确收益时按需制作；玄幻仙侠武打不做多格故事板，使用高细节逐镜提示词。续镜需画面锚定时，从已审核视频抽帧，登记来源与时间码，并绑定首帧或尾帧专用输入。
6. 校验项目清单和当前服务能力；只有授权范围与预算明确时才提交生成。
7. 审核实际媒体，完成剪辑、声音、字幕、技术检查和交付记录。

### 资产提示词调用

人物、场景、法器和武器资产先读取 `references/visual-style-and-asset-modules.md`，按资产类型、视觉风格、题材身份和环境状态组合短模块；国漫、BJD、UE5、PBR 都是可选维度，不得默认写死。

人物造型采用“读取适用库→整套方案比较→唯一造型记录→完整提示词→审美与冲突审核”的流程，详见 `references/character-styling-review.md`。主角吸引力从脸部、剪影、配色与气质共同建立；华丽度按角色选择。文字审核与生成后的图像验收分开，不承诺仅靠提示词保证观众留存。

编写人物四视图提示词时，先读取 `character-archetype-wardrobe-library.md`，把世界约束、身份/职业、剧情功能、主配角层级、气质、个人审美、关系阶段、场景、动作与状态分轴组合，再形成完整 Look Card。未明确写配角/NPC/路人/侍从时，默认按男主女主的高精美标准编译；粗麻烂布或破旧素衣必须有明确剧情依据。明确说玄幻修仙、仙侠或修真时，自动采用仙侠高精美方向，落实门派/修行服制、精致层叠面料、灵纹或法器挂点、玉石金属织物材质分层和发冠簪饰结构。题材不绑定固定角色或固定衣柜；灵异可以有甜妹，末世可以有明星，校园可以承载虐恋。校园角色先确定校服/私服设定和季节；设定为学院制服时保留完整制服体系。腿部层可光腿、短白袜或按设定选择其他袜型；鞋型从场景和制服出发，黑丝袜与厚底大头鞋没有默认优先级。再读取 `face-archetype-library.md`，独立确定骨相路径、气质与五官并和同作品其他角色区分。甜美气质不等于圆脸；配角也要完整好看，但视觉焦点略低于主角。随后读取 `visual-assets.md`、`face-design-and-opulence.md`、`palette-costume-jewelry.md`、`hair-style-library.md`、`hair-color-library.md` 和 `eye-makeup-library.md`。每套造型必须包含完整上衣层次、裤/裙/裙裤下装、腰肩腕部结构、鞋履、袜类/腿部层、饰品与头发；不能只给上衣或题材标签。角色有额彩、花钿、面纹、封印或疤痕时，再读取 `facial-markings-library.md`；没有时明确记录为无。把实际选择的细节写入同一条四视图提示词，不把整个词库复制进提示词。玄幻修仙主角法器读取 `xianxia-hero-artifacts.md`。

资产图采用逐张生成流程：单次只提交一张，展示结果并等待用户确认后再继续；不轮询、不批量并行、不自动重试。详见 `references/sequential-asset-generation.md`。

人物四视图基准板双手空置，剧情道具在道具资产和视频分镜阶段绑定。袜类从长度、材质、渐变、蕾丝、蝴蝶结等结构选择，按角色与鞋履编成一套；不把任何袜型当作默认。

## 目录

| 路径 | 内容 |
| --- | --- |
| `SKILL.md` | 入口、执行边界和端到端工作流 |
| `references/h3-prompt-compiler.md` | H3 模式、字段、对白与提示词编译规则 |
| `references/official-h3-conformance.md` | 官方模型与提示词标准映射、时长及素材上限 |
| `references/story-development.md` | 故事、剧本、台词及情绪推进 |
| `references/voice-profile-and-continuity.md` | 角色音色档案、情绪变化边界、跨 job 锚点和审听验收 |
| `references/h3-episode-production.md` | 剧本至job的段卡、动作/对白负荷、跨段交接、审片与最小返修 |
| `references/genre-production-matrix.md` | 种田、末世、规则怪谈、都市言情、异能、高武、武侠、仙侠与古风的生产卡、状态账本、场景尺度、资产/分镜映射和验收项 |
| `references/script-review.md` | 剧本审查、修补、复审和多集状态台账 |
| `references/visual-assets.md` | 角色、场景和道具资产提示词与绑定规则 |
| `references/visual-style-and-asset-modules.md` | 四个平台调研提炼的多风格视觉资产模块、短模板和环境调用表 |
| `references/face-design-and-opulence.md` | 脸型五官设计、女主脸型偏圆排查与华丽服饰 |
| `references/character-archetype-wardrobe-library.md` | 角色类型的气质转译与全套服装造型决策，覆盖发型、上下装、裤裙、鞋袜、饰品及状态变体 |
| `references/xianxia-manju-costume-library.md` | AI 漫剧玄幻修仙/仙侠服饰槽位组合库：廓形、纱质面料、层搭、露肤与开衩、外披肩部、鞋履、腿足点缀、头面腰佩，以及仙子/圣女/仙君/魔君/妖皇等角色分支与结构层差异化硬约束 |
| `references/modern-manju-costume-library.md` | AI 漫剧都市现代服饰槽位组合库：廓形、面料、层搭、露肤与开衩、外层与肩部、鞋履、腿部层与袜、配饰承载，以及清冷千金/温柔初恋/明艳主角/学院/职场精英/霸总权贵/温柔男友/偶像艺人/街头轻亚/都市异能/晚宴礼服等角色分支与结构层差异化硬约束 |
| `references/face-archetype-library.md` | 角色类型对应的脸型骨相、五官比例、识别点分配和跨角色区分 |
| `references/palette-costume-jewelry.md` | 配色、服装、鞋袜与饰品描述 |
| `references/hair-style-library.md` | 发型剪裁、束发、盘发、编结与视图一致性 |
| `references/hair-color-library.md` | 发色、渐变拓扑、分区和发丝材质 |
| `references/eye-makeup-library.md` | 眼妆分区、色彩、强度与状态变化 |
| `references/facial-markings-library.md` | 花钿、额印、面纹、封印与疤痕 |
| `references/scene-direction-library.md` | 七类题材的场景设计方向 |
| `references/xianxia-hero-artifacts.md` | 玄幻修仙主角级武器与法器设计 |
| `references/directing-and-continuity.md` | 分镜、表演、空间和连续性 |
| `references/action-sound-edit.md` | 动作、特效、声音与剪辑 |
| `references/project-contract.md` | `project.json` 字段与状态契约 |
| `references/quality-and-release.md` | 制作质量门与交付验收 |
| `references/storyboard-preflight.md` | 有明确预演收益时使用的可选剧情故事板；玄幻仙侠武打不使用多格故事板 |
| `references/sequential-asset-generation.md` | 资产图逐张生成、费用与确认规则 |
| `scripts/validate_project.py` | 不调用 provider 的项目清单校验器 |
| `scripts/test_validate_project.py` | 项目清单校验器测试 |

## 本地校验

在仓库根目录运行 `python -m unittest discover -s scripts -p "test_*.py"`；测试运行日志和生成的样例必须保存到 `E:\Test-data-Skill\<project_id>\99_logs\`，不要写入仓库。正式项目清单仍运行 `python scripts/validate_project.py <项目目录>/project.json`；测试项目清单和测试提示词应放在外部测试批次目录。

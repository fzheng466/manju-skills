# Seedance 2.0/2.5 漫剧制作 Skill

面向 16:9 横屏漫剧项目的 Seedance 2.0 / 2.5 端到端制作工作流，覆盖立项与模型锁、故事与剧本、视觉资产、导演分镜、按版本编译提示词、项目校验、生成与修复、剪辑交付。

本 Skill 只管理 Seedance 2.0/2.5 的模式、时间戳语法、素材槽位和调用边界。MiniMax H3 的 T2VA/Ref2VA、`(Sx)`、`<d>` 等字段与配额不适用于本 Skill；用户选择 H3 时转到 `$minimax-h3-manju`。一个项目和 job 只锁定一个版本，版本切换须从中性镜头表重新编译，禁止只替换模型名。服务能力随 provider 和接口变化，实际提交前须核验当前文档与 schema。

完整单集目标为 90–180 秒，由多个生成段连续承载。剧本冻结前按证据审查因果、人物、关系、道具和可视听性；台词冻结后逐字传递，相同 utterance ID 的片段按顺序拼接。

## 安装与调用

将本仓库目录复制到技能目录并保留仓库内的目录结构：

```text
~/.trae-cn/skills/seedance-manju/
```

Windows 默认目录通常为 `%USERPROFILE%\.trae-cn\skills\seedance-manju`。随后在对话中调用 `seedance-manju`。

用户未指定视频模型时，第一步先询问“本次走 Seedance 2.0、Seedance 2.5 还是 MiniMax H3？”并等待回答；锁定版本后才编译对应提示词。所有人物板、资产、分镜和视频输出固定 16:9；人物默认一人一张四视图板（左侧超大正面胸像，右侧正面全身、45° 侧向全身、背面全身）。

## 工作流

1. **P0 立项与模型锁**：记录任务范围、`seedance-2.0` 或 `seedance-2.5`、16:9、题材/风格、目标时长、输出位置、生成授权、费用与返修预算。只有用户明确授权指定 job ID 与预算上限才允许提交。
2. **P1 故事、剧本与诊断**：原创、小说改编或剧本诊断，冻结台词与情绪线；按需读取剧本审查与故事开发参考。
3. **P2 视觉圣经与资产设计**：先读多风格模块定媒介方向，按角色读取造型库、骨相库、妆发库、配色饰品库；服饰按题材读取仙侠或都市服饰槽位库，主角法器读取器物库，造型定稿后执行一致性审核，最终形成同一张四视图人物板；场景按题材读取场景方向库。资产图逐张生成，每张展示结果并等待用户确认后再继续，不轮询、不批量、不自动重试。
4. **P3 导演分镜与动作设计**：逐镜记录起止时间、景别、人物画面占比、视点、机位运动、站位、表演、台词、声音、入出镜态和切镜理由。玄幻仙侠武打不用多格故事板，改以逐镜高细节动作提示词控制。
5. **P4 按版本编译（不可混用）**：锁定 `seedance-2.0` 只读 `references/seedance-2.0.md`，锁定 `seedance-2.5` 只读 `references/seedance-2.5.md`；提示词字段、模式、素材额度、时长、音频能力不得跨版本复制。
6. **P5 验证、生成与修复**：先运行 `project.json` 校验与单元测试，测试产物一律写入 `E:\seedance-text-push\`（禁止进入项目目录）；`submit` 必须有已核验 capability 记录、真实文件映射和明确授权。状态 `planned → assets-ready → submitted → generated → reviewed` 只由真实事件推进，只返修失败镜头，预算用尽即停。
7. **P6 剪辑、声音与交付**：只组装已审镜头，对白、OS/VO、环境、动作音、配乐与字幕分轨处理；核验总时长、16:9、字幕与片段顺序后交付。

## 目录

| 路径 | 使用步骤 | 内容 |
| --- | --- | --- |
| `SKILL.md` | 全流程 | 入口、执行边界和 P0–P6 端到端工作流 |
| `references/seedance-2.0.md` | P4 | Seedance 2.0 专属编译规则：时间戳、模式、素材槽位 |
| `references/seedance-2.5.md` | P4 | Seedance 2.5 专属编译规则：整秒时间戳、三通道控制、首尾帧与多轮延长 |
| `references/research-basis.md` | P4 | 公开资料依据与证据边界 |
| `references/story-development.md` | P1 | 故事开发与剧本冻结 |
| `references/script-review.md` | P1 | 剧本诊断与修订 |
| `references/visual-assets.md` | P2 | 视觉圣经、角色板与场景资产 |
| `references/character-prompt-style-variants.md` | P2 | 本地迁入的完整风格模板矩阵 |
| `references/male-character-asset-design.md` | P2 | 3D半写实男主骨相、体态、服装、华丽度与审核 |
| `references/asset-research-basis.md` | P2 | 迁移来源、四平台检索状态与证据边界 |
| `references/visual-style-and-asset-modules.md` | P2 | 多风格视觉资产提示词模块 |
| `references/character-archetype-wardrobe-library.md` | P2 | 角色类型、气质与全套造型库 |
| `references/character-styling-review.md` | P2 | 人物造型定稿与提示词一致性审核 |
| `references/face-archetype-library.md` | P2 | 角色类型、脸型骨相与五官设计库 |
| `references/face-design-and-opulence.md` | P2 | 脸型五官与华丽服饰设计 |
| `references/palette-costume-jewelry.md` | P2 | 配色、服装与饰品描述库 |
| `references/hair-style-library.md` | P2 | 人物发型结构库 |
| `references/hair-color-library.md` | P2 | 人物发色与发丝材质库 |
| `references/eye-makeup-library.md` | P2 | 人物眼妆设计库 |
| `references/facial-markings-library.md` | P2 | 脸部印花、花钿与法纹库 |
| `references/xianxia-manju-costume-library.md` | P2 | 玄幻修仙/仙侠服饰槽位组合库 |
| `references/modern-manju-costume-library.md` | P2 | 都市现代服饰槽位组合库 |
| `references/xianxia-hero-artifacts.md` | P2 | 玄幻修仙主角武器与法器资产设计 |
| `references/scene-direction-library.md` | P2 | 七类题材场景方向与提示词词库 |
| `references/sequential-asset-generation.md` | P2 | 资产图逐张生成、参考绑定与费用门 |
| `references/directing-and-continuity.md` | P1、P3 | 分镜、表演、空间与连续性，含双人对话、文戏表演链、FPV 一镜到底、多人群戏配合 |
| `references/xianxia-martial-action-prompting.md` | P3 | 玄幻仙侠武打动作提示词，含力量传导、多人破围、快速运镜参数、大招特效参数化 |
| `references/storyboard-preflight.md` | P3 | 剧情故事板预演（按需可选） |
| `references/episode-production-and-continuity.md` | P3、P5 | 单集生产与片段连续性 |
| `references/action-sound-edit.md` | P3 | 动作、特效、声音与剪辑执行手册 |
| `references/vfx-event-design.md` | P5 | 特效事件与可见因果 |
| `references/voice-performance-continuity.md` | P5 | 角色声音与台词表演连续性 |
| `references/project-contract.md` | P5 | `project.json` 字段与状态契约 |
| `references/quality-and-release.md` | P6 | 质量门、审片与交付 |
| `agents/openai.yaml` | 配置 | Agent 运行配置 |
| `examples/` | 参考 | 项目样例与提示词样例 |
| `scripts/validate_project.py` | P5 | 不调用 provider 的项目清单校验器 |
| `scripts/test_validate_project.py` | P5 | 项目清单校验器测试 |

## 本地校验与测试隔离

在仓库根目录运行：

```powershell
python -m unittest discover -s scripts -p "test_*.py"
python scripts/validate_project.py <项目目录>/project.json
```

`draft` 只验证制作计划和版本内结构；`submit` 要求已核验的 capability 记录、真实文件映射和用户明确授权。

**测试隔离硬规则**：凡是测试——单提示词试跑、单元测试、资产生图测试、全流程测试及其输入副本、输出、抽帧、日志和报告——统一放在 `E:\seedance-text-push\` 下，每个测试一个独立子目录，格式为：

```text
E:\seedance-text-push\YYYYMMDD-HHmmss_<kind>_<slug>\
  ├── input\      # 测试项目清单、测试提示词
  ├── output\     # 生成媒体、抽帧
  └── 99_logs\    # 运行日志、测试样例、报告
```

`kind` 取 `prompt`（提示词试跑）、`asset`（资产生图测试）、`pipeline`（全流程测试）、`unit`（单元测试）。测试产物不写入真实项目目录，也不写入本仓库；真实项目运行时绝不在项目目录内创建测试内容。该规则同时写入 `SKILL.md` 的执行原则与 P5 校验章节。

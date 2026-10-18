---
name: seedance-manju
description: "漫剧 Seedance 2.0/2.5 全流程（2026-10 优化版，支持 16:9 与 9:16）。从大纲到资产图、分镜、Seedance 提示词；也可从已冻结的 H3 导演谱转编译。用户说走 Seedance、SD、$seedance-manju、最新 SD skill 时使用。开场第一问锁定交付画幅，再做渠道面谈；2.5 的 30 秒/50 参考图等数字未经渠道核实不得当硬限制。"
metadata:
  version: "2.0.0"
---

# Seedance 漫剧制作

## 第一步：先锁画幅，再面谈渠道（强制）

写资产图或 Seedance 提示词之前：读 `_core/references/channel/interview.md` 与 `_core/references/assets/aspect-tracks.md`。第一问锁定 16:9 / 9:16 / 两条都要。再选渠道。一条线渠道不支持该画幅时只暂停该线。生成 lock：`python -m core.lib.lock --project project.json --channel <id> --baseline models/seedance-2.0.baseline.json --out effective-capability.lock.json`（2.5 换对应 baseline）。提交前：`python scripts/validate_project.py project.json --lock effective-capability.lock.json`。

从 H3 复用同一素材时：中性导演谱才是输入，不要硬翻 H3 成品文本。

```text
python -m core.lib.transpile --project project.json --job-id JOB001 --profile seedance-2.5 --out sd-prompt.md
python scripts/transpile_h3.py --project project.json --job-id JOB001 --profile seedance-2.5 --out sd-prompt.md
python -m core.lib.asset_prompt --kind character --aspect 16:9 --sex female --character-id LIN_WAN --file asset-hero.md
python -m core.lib.identity --project project.json
# 人物卡必须 presentation_sex=male|female；服装/道具必须 owner_id，禁止男女资产串套。
python -m core.lib.shot_quality --job project.json --job-id JOB001 --prompt sd-prompt.md
```

映射表 `references/transpile/field-map.md`；风格层 `references/aesthetic/`。禁止把 `<d>` `(Sx)` `T2VA` 带进 Seedance 正文。

动漫/3D 资产：`_core/references/assets/anime-3d-asset-lexicon.md`。

## 目标与隔离

本技能服务 Seedance 2.0 或 Seedance 2.5 的漫剧制作，交付画幅由开场第一问锁定（16:9、9:16 或两条都要）。用户只说“做漫剧/跑总流程”且未指定路线时，第一步询问“本次走 Seedance 2.0、Seedance 2.5 还是 MiniMax H3？”并等待回答；未回答前可整理材料，不能写视频投喂词或调用。如果用户选择MiniMax H3，停止此流程并转到 `$minimax-h3-manju`，不得在此生成H3内容。用户明确指定Seedance版本或本项目本轮已锁定版本时，直接记录，不重复询问。一个项目和job只能使用一个`model_profile`；版本切换须从模型无关剧本/分镜重新编译，禁止只替换名称或自动回退。

MiniMax H3 是另一条独立技能。用户选择 H3 时提示 `$minimax-h3-manju`；不得在本文件输出 H3 的 T2VA/Ref2VA、`(Sx)`、`<d>`、H3配额或字段。

人物身份四视图可跨画幅共用；构图资产、分镜构图和视频输出按交付线画幅生成（16:9 / 9:16）。人物默认一人一张四视图板：左侧超大正面胸像，右侧并排正面全身、45°侧向全身、背面全身；严禁默认扩成多张头像、九宫格或表情板。只有用户明确需要或单张图确实无法表达结构时才增加资产。规则见 `_core/references/assets/aspect-tracks.md`。

## 执行原则

- 以用户原文、冻结剧本、已确认设定和真实可读参考资产为事实来源；推断、设计补全、未知分别标记。未能打开图像时不声称已分析它。
- 先完成当前范围的依赖，复用有效资产。单镜任务不强制做整季表；用户要完整流程时必须完整交付，不得用“同上/其余同理”省略后半。
- 台词冻结后逐字传递。所有镜头中相同utterance ID的片段按顺序拼接，必须与原文逐字相等；OS/VO与画内对白分开标识。
- 图像提示词、视频提示词、平台请求、已提交任务、生成媒体、审核通过和发布批准是不同产物状态。
- 运行时以当前provider/model_id的文档和工具schema核对模式、时长、素材角色、数量、比例、声音支持与参数。未核实的“官方”社区说法不写成接口事实；schema未知时只交文本草稿。
- 只为高复用、身份敏感、空间复杂或连续性风险准备参考图。复杂动作先用可审阅的文字动作链和状态表排查因果，再按镜号局部修复；不默认生成多格故事板图片。玄幻仙侠武打按 references/xianxia-martial-action-prompting.md 编写高细节提示词。
- 测试隔离：凡是测试——单提示词试跑、单元测试、资产生图测试、全流程测试及其输入副本、输出、抽帧、日志和报告——统一放在 `$MANJU_HOME/test-runs/`（默认 `~/.manju/test-runs/`）下，每个测试建立独立子目录，目录名格式为 `YYYYMMDD-HHmmss_<kind>_<slug>`（kind 如 `prompt`、`asset`、`pipeline`、`unit`）。测试产物不写入真实项目目录、不写入技能仓库；真实项目运行时也绝不在项目目录内创建测试内容。测试目录与路径细则见 P5。

## 制作流程

### P0 立项与模型锁

记录本轮任务范围、`seedance-2.0`或`seedance-2.5`、交付画幅（16:9 / 9:16 / 两条都要）、题材/风格、语言、目标时长、输出位置、生成授权、费用与返修预算、已给文本/图像/视频/音频。只有用户明确要求对指定job ID执行生成并确认预算上限，才记录生成授权；“跑完整流程”或索要提示词不等于允许提交。不能推断但会改变走法的关键选项只问一次。任何模型参数之前确认它属于当前版本和当前接入。

### P1 故事、剧本与诊断

原创整理主角、目标、阻碍、代价、世界规则、因果转折和结尾兑现；小说改编建立事件/伏笔/原文覆盖表；已有剧本先做诊断而非擅改。剧本按场次写可见行动与完整对白，并标明情绪起点、触发、变化/压制与结束状态；情绪设计和表演拆解见 `references/story-development.md` 与 `references/directing-and-continuity.md`。冻结前按需读取 `references/script-review.md`，以证据检查因果、人物与关系、空间状态、可视听表达和制作负荷。完整单集与分镜总长固定为90–180秒；局部片段注明非完整单集。对白时长通过试读或明确标为估算，容不下就给出拆集/扩时/压缩选项，不偷偷加速或删句。

### P2 视觉圣经与资产设计

资产基准来自用户本地 MiniMaxH3 共享资产规范，在本仓库独立维护，不运行时跨目录混用。资产范围固定为 AI 漫剧3D半写实。人物先读 `references/character-prompt-style-variants.md`，按同一风格的完整条件编译；保留源规范的题材默认与可选项，不只摘抄风格表单行。完整交付格式在 `references/visual-assets.md`，男主额外读取 `references/male-character-asset-design.md`，与女主执行同等完成度。旧平台摘要和本次新增设计的依据见 `references/asset-research-basis.md`。只要求优化技能或编写提示词时不调用图像/视频生成。

建立项目固定媒介、色卡、材质、用光和构图方向，先读 `references/visual-style-and-asset-modules.md` 按资产类型、视觉风格和题材身份组合短模块，不把国漫、BJD、UE5、PBR 等维度默认写死。人物资产提示词必须按需读取并实际应用以下库：`references/character-archetype-wardrobe-library.md` 先编译完整 Look Card，分离世界条件、身份、剧情功能、角色层级、气质、个人审美、关系阶段、场景和行动需求；`references/face-archetype-library.md` 选择骨相路径并确保角色间差异；`references/face-design-and-opulence.md` 细化五官、妆容及华丽度；`references/hair-style-library.md`、`references/hair-color-library.md`、`references/eye-makeup-library.md` 分别约束发型、发色和眼妆；存在额彩/花钿/面纹/印记时读取 `references/facial-markings-library.md`，不存在则明确写无。再读 `references/visual-assets.md` 与 `references/palette-costume-jewelry.md`。从库中按角色选择相容细节，不能将库名当标签，也不能把词条随机拼接或全量堆入提示词；最终统一写成同一张四视图人物板，覆盖脸型、发妆、内外上衣层、裤/裙、腰肩腕、鞋袜、配饰及四视图一致性。场景提示词按题材读取 `references/scene-direction-library.md`，覆盖现代都市、古代宫廷、玄幻修仙、武侠江湖、末世灵异、校园言情和未来科技。单一角色只设一个主母题和必要辅母题。

服饰槽位按题材分派：明确玄幻修仙、仙侠或修真时读取 `references/xianxia-manju-costume-library.md`，都市/现代题材读取 `references/modern-manju-costume-library.md`，均按廓形、面料、层搭、露肤、外层、鞋履、腿部层、饰品的槽位组合并满足结构层差异化硬约束；玄幻修仙主角的武器与法器读取 `references/xianxia-hero-artifacts.md`，按器物等级与三层签名递进设计。全部人物造型定稿后，按 `references/character-styling-review.md` 执行“读取适用库→整套方案比较→唯一造型记录→完整提示词→审美与冲突审核”，并核对最终四视图提示词与造型记录一致。

场景依 `references/visual-assets.md` 默认制作一张四向基准板（结构可按主线画幅），实际视频取对应方向单视图；9:16 从该格裁中心竖条或单独出竖幅场景图，禁止拉伸。按“家族→区域→固定结构→状态变体→实际机位”组织；道具按结构比例、握持方式、材质、状态变化登记。只有真实查看过图才填“已核验”；参考图注明控制用途及不控制的内容。资产目录记录 ID、版本、来源、父版本、画幅、尺寸、哈希/路径、状态和镜头用途。

全部资产提示词定稿后，用户一句“开始生图/按清单生图”即可启动逐张实际生成，不要求重复粘贴提示词。必须走 `python -m core.lib.asset_gen next --project project.json --channel <本机档案id> --budget <n>`，确认后再加 `--confirm`。每次仅生成一张当前交付线画幅的资产图；参考图绑定依据身份/结构连续性自主判断，并在调用前告知参考资产与用途。每张生成后展示结果、等待用户确认，再进入下一张。费用、失败重试和禁止轮询规则见本技能自有副本 `references/sequential-asset-generation.md`；不得批量并行、轮询或自动重试。真实渠道只问本机 `$MANJU_HOME/channels`。

### P3 导演分镜与动作设计

每个 shot ID 为一个可审查镜头，记录起止时间、主要可见动作、叙事目的、景别、人物画面高度占比、视点/当前焦点、场景锚点与前中后景、摄影机位置/朝向/运动路径、角色站位/身体方向/视线/持物手、表演触发/可见变化、原台词与语气、声音事件、入镜态、出镜态、切镜理由和连续性来源。每场先确定谁带领观众观察，随后依据可见事件转移焦点；逐镜明确景别和人物占画面高度的大致比例，避免全场固定中景或人物过大。比例建议、景别变化与主客观视点的执行规则见 references/directing-and-continuity.md。机位运动区分推轨、变焦、摇摄、横移、升降；动作写明起手、目标、运行路径、接触/避让、受力反馈和结束姿态，不用“电影感”替代可拍指令。先写中性镜头表/片段卡，再编译当前版本提示词；段卡、负荷、真实片段末态与修复顺序见 references/episode-production-and-continuity.md。玄幻仙侠武打不制作或要求多格剧情故事板图，改以逐镜头的高细节动作、表演、特效、声音和接缝提示词控制；具体规范见 references/xianxia-martial-action-prompting.md。其他题材只有在文字镜头表仍无法核清剧情顺序、且图片预演有明确收益时，才按需读取 references/storyboard-preflight.md；故事板图不是默认阶段，也不因模型支持多格输入而自动加入。

根据 S0–S4 空间复杂度和 A0–A3 资产投入等级决定是否做调度图、动作预演和母场景；级别是减风险的决策工具，不规定每集出图数量。分镜、表演与空间核验见 `references/directing-and-continuity.md`；动作/法术/声音/剪辑见 `references/action-sound-edit.md`。

### P4 按版本编译（不可混用）

根据锁定版本只读其对应文件，并以 `references/research-basis.md` 追溯外部经验的证据边界：

- Seedance 2.0：`references/versions/2.0.md`
- Seedance 2.5：`references/versions/2.5.md`（无来源数字只在 `references/research-basis.md` 待核验区）

两版可以沿用同一中性镜头数据和制作表头，但最终投喂内容必须分版生成。两版共用已确认的剧本审查、角色表演、动作因果、观察视点与人物画面尺度、段卡、资产映射、末态连续性及逐镜QA方法。玄幻仙侠武打不因2.0或2.5的接口能力而恢复默认多格故事板图；具体制作以逐镜高细节提示词为准。提示词字段、模式、素材槽位/额度、时长、音频能力、编辑/续写能力和请求参数不得跨版本复制。每个项目锁定一个版本，版本文件之间不相互引用或借用其语法；变更版本时从中性镜头表重新编译。Seedance 2.0与2.5共有能力也须分别在各自provider中核验。

每个任务的请求清单与提示词正文分开保存。请求清单含实际上传文件到平台槽位的映射、provider、精确model_id、模式、比例、时长、参数及证据日期；项目内部ID不能假冒平台槽位。完整输出模板和版本禁用项在对应分版参考文件。

### P5 验证、生成与修复

长项目用 `project.json` 记录 manifest。调用前运行：

```powershell
python -m core.lib.lock --project path\to\project.json --channel <id> --baseline models\seedance-2.0.baseline.json --out path\to\effective-capability.lock.json
python scripts/validate_project.py path\to\project.json --lock path\to\effective-capability.lock.json
python -m unittest discover -s scripts -p "test_*.py"
```

测试隔离规则：单提示词试跑、单元测试、资产生图测试、全流程测试及其输入副本、输出、抽帧、日志和报告，一律输出到 `$MANJU_HOME/test-runs/YYYYMMDD-HHmmss_<kind>_<slug>/`；`kind` 取 `prompt`（提示词试跑）、`asset`（资产生图测试）、`pipeline`（全流程测试）、`unit`（单元测试/校验器测试）。测试运行日志和生成的样例写入该子目录的 `99_logs\`，测试项目清单与测试提示词放在同级 `input\`，生成媒体放 `output\`。严禁把测试产物写入真实项目目录或技能仓库；真实项目运行时也绝不在项目目录内创建任何测试内容。正式项目的 manifest 校验不在此列，仍针对项目自身的 `project.json` 执行。

`draft`只验证制作计划和版本内结构；任何能力快照都不能作为当前接口的硬限制。`submit`必须有当前接入的已核验 capability 记录（含最短/最长时长、比例、输入类型与声音能力）、真实文件、实际槽位，以及用户明确授权且与提交job ID完全一致的范围和预算上限。授权或能力记录未知时不提交。2.0和2.5的时长及素材基线分别记录在对应参考文件，逐次调用前复核；单集时长与模型生成任务时长分开管理。内容长于当前单任务上限时按语义与动作阶段拆组，保留台词和段缝状态，不切换模型。对白/音色表演原则见 `references/voice-performance-continuity.md`；只有当前版本和服务支持时才使用原生声音输入/语法。玄幻、异能或规则异常特效可读 `references/vfx-event-design.md`，不将特效系统概念冒充模型的底层能力。资产图生成独立执行单张费用门、逐张用户确认、无轮询和无自动重试规则，见 `references/sequential-asset-generation.md`；视频生成授权不自动扩大到资产图或反之。

状态依次为`planned → assets-ready → submitted → generated → reviewed`；只有真实事件才能推进。每个返回片段记录生成ID/路径、版本、参数和审核时间码。问题按身份、构图、空间、动作、对白/口型、声音、技术规格分级；只返修失败镜头，锁定通过内容，保留原始提示词和修订差异。预算用尽即停。

### P6 剪辑、声音与交付

先只组装已审镜头，明确转场、声音桥和连续性接缝。对白、OS/VO、环境、动作音、画内音乐、画外配乐与字幕分轨处理；不要把视频抽出的混音误称为干净人声，也不默认跨段音乐连续。完成后核验总时长、该交付线画幅（16:9 或 9:16）、画面与声音、字幕、片段顺序和端点；技术检查与人工内容审阅分开记录。交付文件、实际规格、审核状态、未完成项和修订记录。详细门槛见 `references/quality-and-release.md`。

## 项目目录与资源导航

完整项目可用：`00_brief/ 01_story/ 02_assets/ 03_shots/ 04_prompts/ 05_media/ 06_edit/ 07_qa/`。根据任务只创建所需内容。字段与机器检查见 `references/project-contract.md`；故事见 `references/story-development.md`；剧本诊断见 `references/script-review.md`；资产见 `references/visual-assets.md`；镜头见 `references/directing-and-continuity.md`；片段连续性见 `references/episode-production-and-continuity.md`；剧情预演见 `references/storyboard-preflight.md`；台词表演见 `references/voice-performance-continuity.md`；特效事件见 `references/vfx-event-design.md`；外部资料依据见 `references/research-basis.md`。锁定Seedance版本后只读其对应编译参考；最终验收见 `references/quality-and-release.md`。人物造型、骨相与妆发库：`references/character-archetype-wardrobe-library.md`、`references/face-archetype-library.md`、`references/face-design-and-opulence.md`、`references/hair-style-library.md`、`references/hair-color-library.md`、`references/eye-makeup-library.md`、`references/facial-markings-library.md`。逐条目说明和机器可读样例见`examples/`。




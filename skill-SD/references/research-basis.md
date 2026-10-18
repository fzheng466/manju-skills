# Seedance 漫剧流程补充的公开资料依据

核对日期：2026-10-12。此清单用于说明哪些制作方法影响了本 Skill；社区案例不构成平台接口或模型能力证明。版本能力以具体 provider、model ID、当前界面/schema和可复现实测为准。

## GitHub 项目

- [Emily2040/seedance-2.0](https://github.com/Emily2040/seedance-2.0)：Seedance 2.0 专属多模态制作工作流。可借鉴逐镜预先定义机位/地标、人物位置与朝向、眼线、单一主动作及末态；后续镜头根据已接受片段的实际状态续接。其示例是否实际渲染需逐例辨认，仓库自述不等于独立实测。
- [LearnPrompt/awesome-seedance](https://github.com/LearnPrompt/awesome-seedance)：分版整理的 Seedance 案例、模板和 Skill 索引。可借鉴按连续时间段写单一主动作、明确参考材料“继承/不继承”的属性、按题材选择低成本文本预演；玄幻仙侠武打以逐镜动作状态和详细提示词核验顺序/构图/时序，再让视频补齐状态过渡；仓库统计与复测结论是维护者自述，不视作接口标准或本项目验收结果。
- [liangdabiao/Seedance2-Storyboard-Generator](https://github.com/liangdabiao/Seedance2-Storyboard-Generator)：剧本、素材清单、镜头表和生成流程的开源示例。可借鉴稳定素材ID及逐镜参考映射；其中固定节奏、固定时长和示例画幅不作为本项目约束。
- [liyue-aigc/seedance-2-5-video-director](https://github.com/liyue-aigc/seedance-2-5-video-director)：Seedance 2.5 独立 Skill 与能力梳理。只作为 2.5 候选模式研究；长视频、续写、编辑、转场、多格故事板和声音等能力需重新在本次 provider 验证后才能进入2.5工作流，绝不转写到2.0。

## 中文平台可见材料

- [Bilibili：Seedance 2.0 AI漫剧全流程课程页](https://www.bilibili.com/video/BV1wJfsBXEB9/)：页面可读作者说明及37节目录，目录覆盖提示词、风格、视角/构图/光影、分镜、图生视频和首尾帧等。这里只核对了课程页说明和目录，没有观看完整课程，故仅将其作为主题线索。
- [Bilibili：Seedance 2.5教程检索结果](https://search.bilibili.com/all?keyword=AI%E6%BC%AB%E5%89%A7%20Seedance%202.5%20%E5%88%B6%E4%BD%9C)：检索页显示独立的Seedance 2.5提示词/图生视频/视听语言教程标题；本次没有观看该教程正文，不能据此确认具体能力。
- [小红书：Seedance 2.0 AI漫剧制作检索](https://www.xiaohongshu.com/search_result/?keyword=Seedance%202.0%20AI%E6%BC%AB%E5%89%A7%20%E5%88%B6%E4%BD%9C&type=51)：搜索页可读到“AI分镜提示词”“AI分镜图做创意动画短片”“25宫格分镜”等标题和互动数；未逐条进入并核实正文或视频，因此不将这些标题作为方法结论。
- [抖音精选：Seedance 2.0 AI漫剧制作检索](https://www.douyin.com/search/Seedance%202.0%20AI%E6%BC%AB%E5%89%A7%E5%88%B6%E4%BD%9C)：结果卡片中，Shine Ai 的 Image2+Seedance 2.0流程说明强调单次片段长度有限、多镜头堆在一个输入中可能乱切或动作衔接不稳，并建议先做导演分镜再拆片段；擎苍与爱的视频描述列出延长、拼接、局部修改、首尾帧等编辑方向。另有独立的 Seedance 2.5 打斗教程卡片。这些只是作者的页面说明/结果摘要，没有完整观看和复现；据此采用“先镜头规划、片段职责清楚、编辑能力逐 provider 核实”的工作原则，不采纳其价格、成片效果或功能保证。
- 知乎“Seedance 2.0 AI漫剧制作”搜索页未读取到具体文章正文，故不引用知乎方法结论。

## 待核验候选（不得当硬限制）

以下来自社区/课程摘要，**必须经当前渠道实测后才能写入 baseline 或渠道档案**：

- 2.5 单次直出 30 秒；2.0 最大 15 秒
- 2.5 参考素材 50；2.0 参考 15
- 2.5 整秒硬切、`[@image_last_frame_*]` 槽位名、MOV 输出、口型 99%+、隐式 3D、「油腻感减少」
- 玄幻打斗用 Midjourney 关键帧驱动（与本 skill「武打不做多格故事板」冲突，默认不用）

## 纳入的共通经验

采用稳定资产映射、每段一条清晰的剧情因果链、具体可见的站位/动作/反应、以真实已审核末态续接、按题材选择纸面预演方式；玄幻仙侠武打以逐镜动作提示词审顺序和动作逻辑、逐段生成后按证据最小返修。所有输入模式、字段、素材数、片长、声音标记和续写/编辑能力均留在各版本文件单独管理；若某种相近功能在两版中都可用，也要在每个版本中独立核验证据与编译方式。


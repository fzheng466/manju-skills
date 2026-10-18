# AIKSK 本地提示词模块索引

本目录融合自 `AI-KSK/aiksk-minimax-h3-local-prompt` 的中文生产规则。它作为 MiniMax H3 漫剧流程的提示词编译增强层使用。

## 使用顺序

1. 先按主 Skill 的项目门、资产状态、导演谱和授权边界确定任务范围。
2. 按真实输入选择模式：纯文本使用 `T2VA`；首帧、尾帧或首尾帧分别使用 `I2VA`、`L2VA`、`FL2VA`；多图/视频/音频语义参考使用 `Ref2VA`。
3. 需要导演台逻辑时读取 `references/director/DIRECTOR_PROMPT_LOGIC_ZH.md`。
4. 涉及武打、双人攻防、兵器或枪斗时读取 `references/playbooks/fight-choreography.md`。
5. 编译时以 `references/h3-prompt-compiler.md` 与 `references/official-h3-conformance.md` 的字段顺序为硬约束；AIKSK 规则是生产启发式，不能替代官方语法。

## 目录映射

- `references/director/`：中文导演台逻辑。
- `references/playbooks/`：中文武打编排规则。
- `references/h3-prompt-compiler.md`：中文 H3 模式与提示词编译规则。
- `references/h3-mode-constraints.md`：模式、字段和参考素材约束。
- `references/official-h3-conformance.md`：官方格式与本地规则的中文映射。

## 边界

源模块中的模型权重、触发词和工作流字段不代表 MiniMax 官方能力，也不自动证明当前服务支持。提交前仍需按主 Skill 核验当前服务格式、真实附件和预算授权。

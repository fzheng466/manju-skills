# MiniMax H3 官方规范映射

本参考把官方 H3 仓库公开的模型和提示词约束映射到本 Skill 的制作流程。项目创作规则（16:9 漫剧、人物调度、微表情和费用门）属于本 Skill 的生产要求；H3 模式、输出范围、提示词字段及素材上限按官方规范执行。

## 核验来源

- 仓库：<https://github.com/MiniMax-AI/MiniMax-H3>
- 本次核验版本：`d21241f0a4b3acbb34c97dae47fa417b7065e438`，提交日期 `2026-08-15`
- 官方 H3 提示词 Skill：`skills/h3-prompt-writing/SKILL.md`
- 基础模式规则：已整理到本 Skill 的 `references/h3-prompt-compiler.md`
- Ref2VA 规则：已整理到本 Skill 的 `references/h3-prompt-compiler.md`
- 模型规格：`README.zh-CN.md` 中“系统概览 / 模型变体和输入规格”

上游仓库持续更新。每次生产提交前仍需检查当前 provider 的接口字段、模式映射、素材计数方式和实际价格；provider 的限制若更严格，取更严格值。provider 若给出更宽值，不扩大官方模型上限。

## 固定遵循的官方标准

- 一个 H3 生成 job 的成片总时长为4–15秒。`project.json` 的 `job.duration_seconds` 按此范围校验，提示词时间线必须与之相等。
- 16:9 是本项目的制作约束。官方模型还支持其他比例，但本 Skill 不开放其他比例。
- 官方基础输出基线为24 FPS、32 kHz立体声音频、默认短边768。provider实际输出或可配置项须单独核验，不能把默认值写成保证参数。
- 输入模式限定为 `T2VA`、`I2VA`、`L2VA`、`FL2VA`、`Ref2VA`。模式名及 H3 checkpoint 概念不能直接推导 provider API 的 `model` 或 `task` 参数。
- 基础模式提示词字段顺序固定为 `integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`；Ref2VA 为 `subject_definitions`、`summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music`。
- 官方提示词 Skill 的示例使用英文正文；H3 模型支持中文对话，本项目采用中文提示词。正文允许中文或英文并默认中文。固定字段名、模式语法、Ref2VA 标签和首帧/首尾帧指令行仍按官方格式生成，台词与画面内真实文字保留原文。
- Ref2VA 输入上限：最多9张图、3段视频、3段音频，混合文件合计最多12个；每段参考视频/音频为2–15秒，各自总时长不超过15秒。音频不可单独作为输入。类型上限采用用户指定的9图、3视频、3音频配置。
- 官方仓库说明 H3-Context-IR 是完整生成系统的重要预处理模块，当前仓库没有开源该模块，并建议将官方能力纳入流程或依提示词指南自行构建预处理。仅当当前 provider 确实提供并核实了 Context-IR 接口时才调用；本地导演谱属于制作侧预检，不宣称复现官方模块。

## 官方标准与项目导演谱

项目的导演谱是内部规划与检查表示，不直接作为 H3 格式投喂。先把站位、出场、动作、表情、对白表演、声音和运镜按时间拆成连续 beats，再将其转换成官方字段中的自然语言提示词；本项目默认中文。不得把内部 JSON 字段名当成官方 API 或提示词字段。

`[Shot N]` 表示一个生成视频内部的剪辑镜头段。一个 job 总时长保持4–15秒，内部剪辑段可以短于4秒；切点按官方时间格式严格递增并位于总时长内。首个 `[Shot 1]` 标签后不加切点时间戳。若项目希望每个分镜行单独生成一个视频，则该行对应一个 job，仍需满足4–15秒。

官方提示词写法提供模型可读的镜头和时间指导，但不保证模型逐帧精确执行。成片仍需逐镜观看，并按实际偏差进行局部修订。

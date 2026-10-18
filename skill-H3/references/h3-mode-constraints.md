# H3 模式与字段约束

本文件整理 MiniMax H3 的基础模式和参考模式约束，作为中文执行规则使用。

## 模式选择

- `T2VA`：只使用文字，生成完整的视听时间线。
- `I2VA`：绑定首帧图片，画面从首帧继续发展。
- `FL2VA`：绑定首帧和尾帧图片，描述两帧之间的连续变化。
- `L2VA`：绑定尾帧图片，描述画面如何从前置状态自然收束到尾帧。
- `Ref2VA`：使用角色、场景、动作、视频或音频等参考素材，并通过语义标签说明素材用途。

## 基础模式字段

基础模式固定使用以下三个字段，字段名和顺序不能改变：

```text
integrated_multimodal_description:
overall_soundscape:
non_diegetic_music:
```

`T2VA` 直接从第一个字段开始。`I2VA`、`L2VA`、`FL2VA` 的对齐指令必须放在提示词第一行，空一行后再写三个字段。对齐时间使用实际视频时长，保留两位小数。

## Ref2VA 字段

Ref2VA 固定使用以下六个部分：

```text
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
```

`subject_definitions` 建立人物、物体或其他主体的稳定身份。相同主体跨多张参考图出现时，使用同一个主体编号。`summary` 说明目标视频和参考素材关系；`retention_analysis` 说明哪些身份、外观、空间或动作需要保留；`detailed_description` 按镜头和时间顺序描述完整动作。

## 编写约束

- 正文默认使用中文；字段名、模式名、主体标签和系统要求的固定标记保持原样。
- 每个镜头必须说明时间、主体、动作、空间位置、摄影机变化和声音结果。
- `overall_soundscape` 只写环境声、动作声和非语言人声，不重复对白。
- `non_diegetic_music` 只写观众听见、画中人物听不见的配乐；没有配乐时写 `N/A`。
- 对白、歌词和画面内文字必须逐字保留，不得在编译阶段擅自润色或删改。
- 不得虚构不存在的参考图片、视频、音频、字段或模型能力。

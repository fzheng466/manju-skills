# H3 → Seedance 字段映射

不要把 H3 成品当输入源。中性导演谱才是真相源。H3 文本只做语义对照。执行：`python -m core.lib.transpile --project project.json --job-id JOB001 --profile seedance-2.5 --out sd.md`。守卫 G-TR1 台词回拼、G-TR2 禁 H3 语法、G-TR3 识别点复述。

图例：机械 / 模板+润色 / 必须重写。

| H3 | 中性层 | Seedance | 类型 |
|---|---|---|---|
| T2VA | job.mode | text_only | 机械 |
| I2VA | first_frame | 2.0 可能 frame_anchored；2.5 first_last 需要双帧否则降级 | 模板 |
| L2VA | last_frame | 通常降级为文字末态 | 重写/降级 |
| FL2VA | 首尾帧 | first_last_frame（能力确认后） | 机械 |
| Ref2VA | references[] | reference_set / reference_image | 机械+截断 |
| `<Subject N>` | assets | 角色名+两项识别点+「参考图锁身份不锁构图」 | 模板 |
| `<d>[lang] 原句</d>` | utterance.text | 角色以语气说：「原句」 | 机械搬运原句 |
| 11 项对白导演 | dialogue fields | 压缩为 3 可听 + 2 可见 | **必须重写** |
| `At 00:03.500` | beats time | 2.0 去精确时间；2.5 整秒（待核验） | 模板 |
| `(Sx)` | speaker_id | 角色名 | 机械 |
| entrance_order | 同左 | 揭示前不得出现名字 | 模板 |
| 服饰形容 | assets | aesthetic 层 | 重写 |

历史项目只有 H3 文本、没有导演谱时：反解析成中性草稿，人工补齐后再进 SD。

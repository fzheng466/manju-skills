# G-CH 渠道守卫

读 `effective-capability.lock.json`，不读裸 baseline。原 G1–G10 保留。

| 编号 | 检查 | 失败 |
|---|---|---|
| G-CH1 | job 时长在 [min,max]；整数秒渠道上时长为整数 | 拦截 |
| G-CH2 | 正文时间表达最大值 ≤ job 时长 ≤ 渠道 max。10s 渠道出现 12s 时间轴 → 拦截 | 拦截 |
| G-CH3 | 各类参考数量 ≤ 生效上限；正文「参考图 N」不超过槽位 | 拦截 |
| G-CH4 | job 模式在渠道 modes 内 | 拦截 |
| G-CH5 | 无音频时正文无声音标记、无「生成对白/配乐」；audio_post_plan 覆盖全部 utterance | 拦截 |
| G-CH6 | 请求画幅在渠道列表；正文画幅词一致 | 拦截 |
| G-CH7 | 正文字数 ≤ prompt_max_chars | 拦截 |
| G-CH8 | 提交时重算渠道/baseline 哈希，与 lock 不同则要求重编译 | 拦截 |
| G-CH9 | failed 能力项拦截；unknown 且必需则拦截；declared/过期允许但标「首次试探」 | 拦截/警告 |
| G-CH10 | 预估费用 ≤ 授权预算；计费 unknown 拦截 | 拦截 |
| G-CH11 | adaptation-report 每条降级都有对应产物 | 拦截 |

成功提交：declared → verified。失败能识别原因：标 failed 并写入真实上限。

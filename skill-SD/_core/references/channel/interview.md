# 开场面谈（画幅先于渠道）

写任何资产提示词或视频提示词之前完成。顺序固定：

1. **交付画幅（项目决定）**
2. **渠道**
3. **模型（渠道支持多个且用户未指定时才问）**
4. **按交付线预览 → 确认 → 写 lock**

生效能力按**每条交付线**分别计算：

```
effective[track] = model baseline ∩ channel ∩ that track's aspect
```

档案只存在本机：`$MANJU_HOME/channels/<id>.json`（默认 `~/.manju/channels`）。**禁止把真实渠道、反代地址、密钥、账号写进仓库或推 GitHub。** 仓库 `examples/channels/` 只放字段模板。调用本 skill 时当场问操作员：渠道档案 ID、本机模型入口；操作员说「本地提供」就只读 `$MANJU_HOME`，不要猜、不要提交。

## 第 1 题（必问，单独一屏）

这次要交付什么画幅？

- 只做 16:9 横屏
- 只做 9:16 竖屏
- 两种都要（横竖两条交付线）

若选两种都要，追问主线：16:9 为主 / 9:16 为主 / 两条完全独立。

写入 `deliverables` + `primary_track`。**这一步不读渠道。**

## 第 2 题：渠道（只问本机，不写进 Git）

先问：「这次用哪份本机渠道档案？路径默认 `$MANJU_HOME/channels/<id>.json`。没有档案就现在填一张，仍只写本机。」

已有档案：摘要卡显示 名称｜画幅｜最长时长｜参考图数（不含首尾帧）｜音频｜最后验证。问「仍然准确吗？」禁止把答案贴进仓库。

新建则一张表：

- 能出哪些画幅（可多选）
- 单次最长时长
- 一次最多几张**参考图（不算首尾帧）**
- 生成视频带不带声音
- 视频时长是区间还是枚举？枚举请列出（如 5/10/15）→ `duration_seconds.allowed`
- 生成视频是否同期出声（对白/环境）？→ `audio_output: native|none|unknown`；模型文档写 `dialogue_and_sfx` / `dialogue` 时按 `native` 别名记录
- 是否允许/本项目是否使用参考音频槽？→ `reference_audio: allowed|forbidden|unsupported`（用户可在 allowed 时仍选 forbidden）
- 参考图输入方式：裸 URL / 必须先上传为平台资产 → `reference_transport: url|uploaded`；平台资产 ID 能否跨账号复用 → `asset_id_portable: true|false`
- 真人风控：是否拒收真人肖像？哪类可过 → `realperson_policy: {identity_board: ok|reject|unknown, face_closeup: …, face_composite: …}`
- 图像分辨率是否同价 → `image_pricing: flat|tiered`；flat 时默认取最高档
- 失败是否退额度 → `refund_on_failure: true|false`

`unknown` 一律当作未核实：提示词可以写，**不能 submit**，也不能自动降级成后期配音。

## 第 3 题：模型

仅当渠道支持 H3 与 Seedance 且用户没指定时才问。

## 第 4 步：按线预览

```
[L 16:9] 渠道 X 支持 ✓｜最长 10s → 预计 N 段｜参考上限 2（不含首尾帧）
[P 9:16] 渠道 X 不支持 ✗ → ①给 P 线换渠道 ②P 线暂停 ③衍生版（canon:false，不替代正片）
```

一条线受阻**不暂停另一条**。全部线选定后才写 `effective-capability.lock.json`。

生成 lock：

```text
python -m core.lib.lock --project project.json --channel <id> --baseline skill-H3/models/h3.baseline.json --out effective-capability.lock.json
```

提交前：

```text
python scripts/validate_project.py project.json --lock effective-capability.lock.json
```

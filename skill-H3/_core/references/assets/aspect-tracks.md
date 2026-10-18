# 双画幅交付线（16:9 与 9:16）

项目画幅是**开场第一问**，不是渠道说了算。可选：只 16:9、只 9:16、两条都要。

`project.json` 示例：

```json
{
  "deliverables": [
    {"track_id": "L", "aspect": "16:9"},
    {"track_id": "P", "aspect": "9:16"}
  ],
  "primary_track": "L"
}
```

## 资产

交付画幅 ≠ 资产图画幅。成片可以是 9:16，**资产图只出一套 16:9，两条线共用**。竖屏默认不裁图、不重生图。

| 资产 | 画幅 | 规则 |
|---|---|---|
| 人物四视图身份板 | **永远 16:9，一套** | 一人一张。9:16 视频直接把这张图当 `<Picture n>` 挂上，不锁构图 |
| 场景四向结构板 | **永远 16:9，一套** | 锚点只在这张上定义。9:16 镜头在提示词里写纵深、锚点落点、人物高度、8% 安全区 |
| 道具/兵器结构板 | **永远 16:9，一套** | 左主图 + 右细节窗。不另出竖版 |
| 首尾帧锚图 | 跟随交付线 | 只有 I2VA/FL2VA 的首尾帧必须是成片画幅的实帧（通常从上一段视频抽） |
| 竖裁参考图 | **失败后才做** | 某镜试跑后被 16:9 参考带成横构图或锚点漂移，才给那一镜补一张竖裁。不是默认步骤 |
| 人物卡 | 共用身份 | 必填 `presentation_sex: male\|female`，提交缺失即拦截 |
| 服装/道具/兵器绑定 | 按角色 | 必填 `owner_id`；专属识别点不得落到别的角色板上。生图走 `asset_prompt --sex --project` |

## 镜头提示词

| 项 | 16:9 | 9:16（手机竖屏，参考图仍是 16:9） |
|---|---|---|
| 开头 | 16:9横屏 | 9:16竖屏 + 请求显式 9:16 |
| 双人 | 左右并排、过肩 | 前后纵深或上下错位，禁止并排 |
| 全身高度 | 65–85% | **60–74%**（旧 75–90 会顶满字幕区） |
| 中景到腰 | 35–70% | **42–58%**，上限 60 |
| 中近景到胸 | 45–80% | **52–66%**，上限 68 |
| 走向镜头 | 不限 | 起步 ≤45%，停在约 3 米，整段变大 ≤18 点 |
| 运镜 | 横移、水平摇可用 | 升降、推拉、竖摇；略长焦，忌齐胸高贴脸 |
| 安全区 | 左右边缘 | 头顶先空约 12%（含上沿 8% 字幕），下沿 8% |
| 参考图 | 16:9 主板 | 同一套 16:9 主板；提示词必须写「只锁身份不锁构图，勿模仿大胸像」 |

剧情 beats、台词、出场顺序两条线共用。构图字段放 `beats[].framing.L` / `beats[].framing.P`。副线构图必须单独审，不能套主线。

## 生产命令

```text
python -m core.lib.asset_prompt --kind character|prop|weapon --aspect 16:9 --sex male|female --file <prompt.md> --project project.json
python -m core.lib.asset_prompt --kind scene --aspect 16:9 --file <prompt.md>
python -m core.lib.shot_quality --job project.json --job-id <id> --prompt compiled.md
python -m core.lib.adapt --job project.json --lock effective-capability.lock.json
python -m core.lib.transpile --project project.json --job-id <id> --profile seedance-2.5 --out sd.md
```

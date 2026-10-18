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

交付画幅 ≠ 资产图画幅。成片可以是 9:16，**主板永远 16:9**。

| 资产 | 画幅 | 规则 |
|---|---|---|
| 人物四视图身份板 | **永远 16:9** | 一人一张主板，L/P 共用。禁止再出一张 9:16 身份板。引用时不锁视频构图 |
| 场景四向结构板 | **永远 16:9** | 锚点只在这张上定义。9:16 从已过审真图取中心竖条（可向锚点偏移），登记 `parent_asset_id` + `crop_box`；短边不够才出 `derivative`，锚点句必须照抄主板，禁止拉伸、禁止把路灯挪到中轴 |
| 道具/兵器结构板 | **永远 16:9** | 左主图 + 右细节窗 |
| 构图派生 / 首尾帧 | 跟随交付线 | `SCENE_<ID>_<方向>_P` 或 `kind: frame`。帧图必须等于成片画幅 |
| 人物卡 | 共用身份 | 必填 `presentation_sex: male\|female`，提交缺失即拦截 |
| 服装/道具/兵器绑定 | 按角色 | 必填 `owner_id`；专属识别点不得落到别的角色板上。生图走 `asset_prompt --sex --project` |

## 镜头提示词

| 项 | 16:9 | 9:16 |
|---|---|---|
| 开头 | 16:9横屏 | 9:16竖屏 |
| 双人 | 左右并排、过肩 | 前后纵深或上下错位 |
| 全身高度占比 | 65–85% | 75–90% |
| 运镜 | 横移、水平摇可用 | 升降、推拉、竖摇为主 |
| 安全区 | 左右边缘 | 上下约 8% 留给字幕/UI |

剧情 beats、台词、出场顺序两条线共用。构图字段放 `beats[].framing.L` / `beats[].framing.P`。副线构图必须单独审，不能套主线。

## 生产命令

```text
python -m core.lib.asset_prompt --kind character|prop|weapon --aspect 16:9 --sex male|female --file <prompt.md> --project project.json
python -m core.lib.asset_prompt --kind scene --aspect 16:9 --file <prompt.md>
python -m core.lib.asset_prompt --kind scene --aspect 9:16 --derivative-of SCENE_<ID> --file <crop.md>
python -m core.lib.aspect_sync --landscape scene.md --portrait crop.md --scene-id SCENE_<ID>
python -m core.lib.shot_quality --job project.json --job-id <id> --prompt compiled.md
python -m core.lib.adapt --job project.json --lock effective-capability.lock.json
python -m core.lib.transpile --project project.json --job-id <id> --profile seedance-2.5 --out sd.md
```

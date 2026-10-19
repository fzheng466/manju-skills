# 双画幅交付线（16:9 与 9:16）

项目画幅和**剧种**是开场前两问，不是渠道说了算。画幅可选：只 16:9、只 9:16、两条都要。

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
| 贯穿特效模板（系统面板/法阵/刃光/护盾/感染/技能槽） | **永远 16:9，一套** | `kind: fx` + `fx_class` + 必填 `owner_id`。左主图+右细节窗；空面板或假字；写明边框/阵纹光源路径。细节窗必须含「人物身边的紧凑态」。9:16 不另出竖版主板 |
| 全屏 UI 插入帧（`fx_class=hud`） | **跟随交付画幅** | `kind: frame` + `derived_from` 主板 + `owner_id`。无字底板，只给「看清菜单」的插入镜作构图。带字成品图只作剪辑/后期，不作生成参考。不是第二张身份主板 |
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

## 剧种 → 必出模板（编译镜头前完成）

`project.json` 写 `"genre": "urban_system|xianxia|xianxia_combat|scifi|apocalypse|isekai_game"` 与 `"fx_templates": [{"asset_id","fx_class","owner_id","first_job"}]`。大纲出现系统/法阵/护盾/刃光/感染/技能栏，而 `fx_templates` 为空，不得进入镜头编译。镜头内可读中文一律后期叠字，生成图只留空槽或假字。

| 剧种 | 必出 `fx_class` |
|---|---|
| 都市异能 / 系统流 | hud（系统面板）；skill_ui 可选 |
| 玄幻修仙 | array + trail（灵气/飞剑路径，与兵器板分开） |
| 仙侠战斗 | trail（刃光）+ shield；兵器板另出 |
| 科幻 / 近未来 | hud + shield |
| 末世丧尸 | infection + hud（战术） |
| 游戏异世界 | skill_ui |

引用方式：`<Picture n>` 只锁面板/法阵外形、材质、边缘光路径与粒子槽，不决定构图。

## 贯穿特效的镜头状态（剧种无关）

效果卡 / fx 资产新增：

- `visibility`: `owner_only`（系统、读心、个人面板）| `scene_visible`（法阵、护盾、刃光、感染）
- 每个 job 写 `fx_state_in` / `fx_state_out`，取值：`off` → `presence`（存在感：光点/细条）→ `readable`（身边可读：半身光幕、菜单可读）→ `fullscreen`（全屏插入，人物不入画）→ `collapsed`（收束到余光/消失）
- `fx_tier_confirmed`: 用户在 look-dev 静帧上确认的档位与尺寸（人物高度%、特效高度%、位置）

档位尺寸（**未确认时用安全默认；确认后以确认值为准**，门禁读确认值）：

| 档 | 16:9 安全默认 | 9:16 安全默认 | 何时用 |
|---|---|---|---|
| presence | 特效 ≤10% | ≤10% | 系统持续在线、人物在做别的事 |
| readable | 特效 25–50%，与人物同框 | 25–45%，人物让出半侧 | 用户要看清且要人和系统同框（触发镜、第一次读菜单） |
| fullscreen | 70–90%，人物不入画 | 纵向堆叠 70–90% | 信息量大、模块多 |

「看清菜单」由 readable 或 fullscreen 二选一，由剧情+用户确认，**不默认插入镜**。完整外壳（标题环+地台+左右装饰列）仍只允许 fullscreen。

可见性编译规则（owner_only）：

1. 本 job `visible_cast` 含非持有者，且该人物在说话或被说话 → `fx_state` 只能是 `off` / `presence` / `collapsed`；进入本 job 前若为 readable，开头 ≤1 秒内收束。
2. 过肩、隔门、正反打对话镜：特效不得位于两人视线连线上。
3. 非持有者的视线、台词、表演不得对特效做出反应（看不见）。
4. 持有者单独的反应镜可以保留 presence/readable；「反应镜带小面板」只在 visible_cast 仅有持有者时成立。规则 1 优先。

转身、侧身、过肩时：特效必须移到余光、缩小或收束（`SHOT-FX-BODY`）。触发镜（持有者单独、正面）不检查这一条。

## 系统 / 全屏 UI 插入镜（跨剧种）

完整外壳仍不要和中景人物同框。未确认档位时用安全默认；用户已确认 readable 后按确认尺寸，不必硬拆插入镜。

画幅差在插入镜的模块排布，不在人物身份板：

| | 16:9 插入 | 9:16 插入 |
|---|---|---|
| 信息流 | 主面板居中，装饰分列左右，地台在底 | **纵向堆叠**：上沿 8% 留空 → 标题 → 少量装饰 → 主面板（宽≈80%）→ 底部模块 → 地台（离底 8%） |
| 禁止 | 把竖构图的上下堆叠硬拉成左右空 | **照搬 16:9 左右各 3 枚装饰列**；把横图裁成竖图当插入帧 |

门禁：`SHOT-FX-TIER` 读确认档位；未确认且人物>50% 且 UI>40% 仍报 `SHOT-FX-UI`。人物镜头出现两种以上完整外壳模块，或 9:16 插入镜写「左右各 3 枚」，仍拦截。

## 参考图用途（ref_role）与绑定表

每个 `asset_bindings[]` 必填 `ref_role`，绑定器按表过滤；一张图只承担一种 ref_role。

| ref_role | 来源 | 视频 references | 首尾帧 | 真人项目 |
|---|---|---|---|---|
| identity_board | 人物四视图 16:9 | 允许 | 禁止 | 允许（渠道 realperson_policy.identity_board=ok） |
| scene_master | 四向 2×2 整板 | **禁止** | 禁止 | — |
| scene_view | 四向板按 view_map 裁的单格 / 单视角重生 | 允许，每镜 ≤1 张主视角 | 禁止 | 允许 |
| prop_board | 道具 16:9 | 允许 | 禁止 | 允许 |
| prop_state | 道具状态卡（盖/揭、开/关、空/满、稳/闪） | 允许，须与 continuity_ledger 状态一致 | 禁止 | 允许 |
| fx_shell | fx 模板空板（无字） | 允许，只锁外形 | 禁止 | 允许 |
| fx_lookdev | 人物+特效构图静帧（已确认档位） | 默认禁止；无脸裁切版允许 | 禁止 | 带脸版**禁止** |
| fx_text_frame | 带冻结字的 UI 静帧（已人工校对） | 只允许全屏插入镜或可读档身边态，且不含人脸 | 插入镜可作首帧 | 不含人脸才允许 |
| tail_frame | 上一镜末帧 | 只允许作首帧 | 允许 | 允许 |

规则：

- `tail_frame` 继承上一镜状态。若本镜 `fx_state` 与上一镜不同（如 owner_only HUD 要收起），尾帧必须先去掉特效，或改用不含特效的帧，否则 `SHOT-REF-INHERIT`。
- 真人风控按渠道 `realperson_policy`，不写死某家：身份板默认可用；单人脸特写和带脸合成静帧默认禁止，渠道明确 ok 才放开。`reference_transport: uploaded` 时，绑定器只输出平台上传后的资产引用，不输出裸 URL；`asset_id_portable: false` 时按账号分别登记。
- 每镜参考图数取渠道上限与「每增加一张都有明确 controls」两者中较小的那个；肢体复杂镜头优先减图。

可读剧情字（冻结 onscreen_text）两条路，job 写 `text_mode`：

- `baked_verified`：先出 `fx_text_frame` 静帧 → 人工逐字核对冻结原文 → 视频绑定该静帧（正面、不含人脸）；乱码/错字退回 `post_overlay`。
- `post_overlay`（默认，也是失败回退）：生成只留空槽/假字，后期叠字。背面、侧斜视角一律 `post_overlay` 或不可见。资产主板（fx_shell）始终无字。

## 生产命令

```text
python -m core.lib.asset_prompt --kind character|prop|weapon --aspect 16:9 --sex male|female --file <prompt.md> --project project.json
python -m core.lib.asset_prompt --kind scene --aspect 16:9 --file <prompt.md>
python -m core.lib.asset_prompt --kind hud --aspect 16:9 --owner-id CHAR_A --file hud-system.md
python -m core.lib.shot_quality --job project.json --job-id <id> --prompt compiled.md --lock effective-capability.lock.json --stage submit
python -m core.lib.adapt --job project.json --lock effective-capability.lock.json
python -m core.lib.transpile --project project.json --job-id <id> --profile seedance-2.5 --out sd.md
```

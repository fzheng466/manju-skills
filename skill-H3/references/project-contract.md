# 项目合同与记录

## 项目文件布局

### 测试与正式项目隔离

正式项目文件可以使用下列项目目录；所有测试文件和测试产物必须放在固定外部根目录 `E:\Test-data-Skill`，不能在项目目录或仓库内创建：

完整项目使用可编辑的项目目录；未做的阶段不创建伪产物。

```text
project/
  project.json              项目、模型锁、台词、资产、任务和审核状态的机器可读真相源
  00_brief/brief.md          范围、风格、受众、预算和来源说明
  01_story/coverage.md       原文/事件覆盖与改编说明
  01_story/episode-01.md     冻结剧本
  02_assets/asset-ledger.csv 资产ID、版本、用途、路径和证据
  03_shots/shot-list.csv     镜头执行表
  04_h3_prompts/job-*.md     H3模式专属提示词正文（不含API载荷）
  05_media/{images,videos,audio}/ 实际返回文件
  06_edit/edit-plan.md       时间线、字幕、声音及转场计划
  07_qa/                     逐镜内容审核和技术报告
```

只做一条提示词时可以直接交付Markdown，不强制建立完整目录。项目清单保留原文件、通过资产和提示词的不可覆盖版本；路径相对`project.json`所在位置。

测试批次使用 `E:\Test-data-Skill\<project_id>\YYYYMMDD-HHmmss_<kind>_<slug>\`，其中 `<kind>` 为 `prompt`、`asset`、`video` 或 `pipeline`。批次内固定使用 `00_meta`、`01_prompt-tests`、`02_asset-tests`、`03_video-tests`、`04_full-pipeline`、`99_logs`；资产测试在 `02_asset-tests` 下再分 `prompts`、`inputs`、`generated`、`reviews`，视频测试在 `03_video-tests` 下再分 `prompts`、`requests`、`outputs`、`reviews`。测试 `project.json`、提示词、媒体、抽帧、请求记录和报告均放在批次目录。`path`、`compiled_prompt_path`、`request_record_path` 只要指向测试对象，就使用该外部绝对路径或相对测试批次根路径，不得指向项目目录。

测试批次必须在 `00_meta\manifest.json` 登记：`project_id`、`batch_id`、`kind`、`created_at`、输入来源、提示词/代码版本、模型与通道、`made_provider_call`、预算、产物目录和结果状态。凭证、令牌和私密配置永不写入测试目录。

## 项目JSON契约

`project.json`顶层字段：

| 字段 | 规则 |
|---|---|
| `schema_version` | 当前合同版本；新项目使用`1.2`，`1.0/1.1`仅用于读取旧草稿并在提交前迁移 |
| `project_id`、`title` | 稳定项目ID与项目名 |
| `pipeline`、`model_profile` | 固定为`minimax-h3`；Seedance标识不允许出现在本包 |
| `aspect_ratio` | 固定`16:9` |
| `stage` | `draft`或`submit` |
| `generation_authorization` | 草稿记录为未授权；提交必须记录用户对精确job ID集合的明确授权、授权证据和非负预算上限/单位，不得由代理推断；job ID集合必须与本次提交清单完全一致 |
| `capability` | 草稿可为null；提交必须写当前服务核验记录：provider、精确model/checkpoint、核验时间、证据位置、16:9支持、已核验模式/输入角色/最短与最长时长；Ref2VA还记各类素材上限 |
| `voice_profiles` | 每个固定发声角色的稳定音色档案、版本/状态、`actor_id`、参考音频资产ID（如有）及测量依据；无实录的声学数值留空/null |
| `utterances` | 按语言单元ID存完整原句、稳定 `speaker_id/actor_id`、`voice_profile_id`、kind、language、情绪态及tone；冻结后不改写 |
| `assets` | 资产ID、类型、状态、比例、版本、用途、来源、实际路径和哈希（若有）；Ref2VA视频/音频另记`duration_seconds`；归档视频记录`generated_by_job_id`与`archived=true`；视频抽帧记录`frame_source`和`represents_asset_ids` |
| `jobs` | 每个生成任务的model_profile、mode、duration、16:9、输入资产ID及用途、`asset_bindings`、状态账本、shots、提示词版本、剧集时间偏移 |

每个job含唯一`id`、`model_profile=minimax-h3`、`mode`、`duration_seconds`、`aspect_ratio=16:9`、`episode_start_seconds`、输入清单`inputs`、`asset_bindings`、镜头`shots`、`prompt_version`和`compiled_prompt_path`。 `continuity_ledger`是该job的镜头状态账本，至少含`world_axis`、`focus_owner`、`visible_cast`、`screen_positions`、`body_and_gaze`、`hands_and_props`、`costume_damage`、`environment_state`、`lighting_state`、`sound_tail`、`action_phase`、`transition_reason`及`previous_job_id`。镜头的`start_state/end_state`与它一致；不存在前镜时`previous_job_id`写`none`并说明开场建立依据。每个生成job时长固定4–15秒，这是官方模型上限；provider若更严则取交集。`inputs`使用`{asset_id, role}`，不直接伪造平台槽位。`asset_bindings`逐项使用`{asset_id, purpose, controls, binding_method}`登记本job实际依赖的角色、场景、道具或锚帧资产；`binding_method`为`attached_reference`（作为Ref2VA附件）、`represented_in_frame`（外观已包含在首/尾帧锚图中）或`frame_anchor`（作为本job的首/尾帧输入）。每个shot列`asset_ids`，只能引用本job的绑定资产；提交阶段所有镜头都须显式列出该字段，可为空数组。提示词中引用的资产ID和用途须能回到此清单及真实附件/锚帧，不能只写在提示词里而没有输入映射。`stage=submit`还需真实提示词正文路径和经核实的`request_record_path`。



### 战斗账本（按需）

战斗、斗法或能力型 job 在`continuity_ledger`之外填写`combat_ledger`：`advantage_chain`（优势方、证据、应对、反转和代价）、`exchange_state`（起点、媒介、轨迹、目标、接触或最近点、结果、受力和恢复）、`ability_lifecycle`（未使用时写`none`）、`peak_event`、`environment_feedback`和`next_action_interface`。普通文戏不添加该字段。

### 连续性状态账本模板

每个 schema 1.2 的 job 在导演谱前填写下列结构；字段值写实际可见状态，不使用“同前”“保持一致”等代词。

```json
{
  "world_axis": "角色A位于场景北侧，角色B位于南侧；攻击与视线的世界方向",
  "focus_owner": "本段主要观察或行动角色",
  "visible_cast": ["当前可见角色ID"],
  "screen_positions": "角色相对场景锚点与画面区域",
  "body_and_gaze": "身体朝向、脸朝向、视线目标",
  "hands_and_props": "左右手、道具形态、交接或开合状态",
  "costume_damage": "服装、伤损与污渍状态",
  "environment_state": "天气、风水火烟、陈设与持续动态",
  "lighting_state": "光源方向、强度与可见变化",
  "sound_tail": "上一段最后仍持续的环境或动作声音",
  "action_phase": "静止、预备、运动中、接触后或收势",
  "transition_reason": "与前段连接或本段建立镜头的原因",
  "previous_job_id": "none 或已审核的前序job ID"
}
```

H3每个job只能选择一种输入模式。Ref2VA的实际附件使用`attached_reference`并映射到`inputs`中`role=reference`；I2VA/L2VA/FL2VA的输入帧本身使用`frame_anchor`并映射到相同ID的首/尾帧输入，画面中需保持的角色、场景、道具使用`represented_in_frame`，且须在对应帧图的`represents_asset_ids`中登记。提交阶段每个`inputs`项都必须在绑定表中有对应关系。首尾帧模式不附加Ref2VA参考图；若绑定资产未出现在帧锚图中，应先制作/审核含有该资产的锚图，或另拆Ref2VA任务，不得混合模式。

归档生成视频作为抽帧来源时，视频资产记录`{kind: "video", status: "approved", archived: true, generated_by_job_id, path, duration_seconds}`；来源job必须为`reviewed`。抽出的帧是独立`kind: "image"`资产，记录`frame_source: {video_asset_id, source_job_id, time_seconds}`及`frame_role: first_frame / last_frame`。时间码须落在源视频有效时长内；帧图比例为16:9，提交前状态为`approved`并能读取。对应帧输入角色仍使用`first_frame`或`last_frame`，并按H3模式写首帧/尾帧专用指令行。抽帧和登记不等于提交新视频job的授权。

新项目的 shot 使用导演谱字段：稳定`id`、job内从0开始的`start_seconds/end_seconds`、`purpose`、单一`main_action`、`start_state`、`end_state`、`continuity_from`、`entrance_order`、`camera_plan`、`performance_plan`、连续`beats`、`dialogue`列表及声音字段。内部 shot 表示成片中的剪辑段，可以短于4秒；shot列表必须连续覆盖4–15秒job时长，不得重叠/倒序/漏时。若每条分镜行独立生成，则该行应单独作为job并遵守4–15秒范围。

`entrance_order`是数组；每项含`actor_id`、`initial_visibility`、`reveal_trigger`、`reveal_start_seconds`、`arrival_seconds`、`path`、`arrival_position`。开场已经可见的人也登记，`reveal_trigger`可写`present_at_start`。`initial_visibility`使用`visible / offscreen / fully_occluded / partial`；首次相遇、伏击和身份揭示不得省略。隐藏人物的`reveal_start_seconds`必须落在 beat 边界；此前不得出现在`positions`可见人物列表中，从该时间起必须进入至少一个 beat 的`positions`。

`camera_plan`含`start_composition`、`camera_position`、`height_angle`、`lens_intent`、`movement`、`movement_trigger`、`movement_path_speed`、`movement_end`、`end_composition`、`cut_policy`。一个 shot 可有切镜，但每次切镜必须在 beats 中标清时间，并在切后重新定义机位；无法清楚表示时拆 shot。

`performance_plan`含`objective`、`concealment`、`trigger`、`baseline`、`micro_expression_sequence`、`body_breath`、`listener_reaction`、`hold_seconds`、`end_expression`。没有听者时`listener_reaction`明确写`none`，不能留空。

`beats`连续覆盖该 shot；每项含`start_seconds`、`end_seconds`、`focus`、`viewpoint`、`cut_reason`、`visible_action`、`positions`、`gaze`、`expression`、`camera`、`audio`、`end_state`。时间使用job本地秒数，必须位于shot范围内。`viewpoint`说明客观观察、角色主观、过肩/反打等视点及当前观察者；无切镜时`cut_reason`写`none`并保持当前镜头。`positions`是当前可见人物列表，每人写`actor_id`、`scene_anchor`、`frame_region`、`screen_height_percent`、`body_orientation`，同时锁定场景位置、画面区域、人物约占画面高度比例与身体朝向。百分比是构图意图，不要求模型像素级精确；大远景可从3–10%、远景10–25%、全身动作镜65–85%、中远景45–70%、中景35–60%、近景55–80%起步，按实际裁切、人物数量和剧情信息调整。`camera`写`framing`、`movement`、`trigger`、`end`；每个 beat 一次只包含一个主运动或明确`locked`，锁定时`trigger`写`none`。连续多个 beat 不应无理由固定中景；切换景别时写切前/切后焦点和空间轴线承接，切镜由可见动作、视线、信息或关系变化触发。

`dialogue`每段写`utterance_id`、原文`text`、稳定`speaker_id`、`voice_profile_id`、`start_seconds`、`end_seconds`、`pre_line_action`、`delivery`、`pause_plan`、`stress`、`cadence_end`、`post_line_reaction`和`listener_reaction`。`delivery`至少给出音量、相对角色基础音色的本句变化、语速、情绪力度与表达策略；身份层声线从`voice_profile_id`引用，不在各句重新发明。H3本段局部`(Sx)`与稳定角色ID的映射另存，不替代项目`speaker_id`。时间位于所属shot内；同一shot的对白不能互相覆盖，除非剧本明确要求重叠。全项目按`episode_start_seconds + dialogue.start_seconds`排序，同一语言单元分散在不同job/镜头中的片段拼接后必须逐字等于完整utterance。只有确实剪断的语句允许显式标记剪断；不要为了方便把旁白伪装成画内对白。

`schema_version=1.0/1.1`的旧草稿可以读取和迁移，但进入`stage=submit`前必须升级为`1.2`并补齐导演谱、人景比例、观察视点和切镜理由。生成任务已经处于`submitted / generated / reviewed`时，项目`stage`不得仍为`draft`。

Ref2VA提交时按H3官方上限校验：最多9张图、3段视频、3段音频，混合输入总数最多12；每段视频/音频2–15秒，视频和音频各自总时长最多15秒；音频不能是唯一输入。当前provider限制更严时，按provider限制执行。

H3的`mode`只允许`T2VA`、`I2VA`、`L2VA`、`FL2VA`或`Ref2VA`。实际`inputs.role`与数量规则见`h3-prompt-compiler.md`；提交时必须同时符合当前H3接口记录。项目清单的模式名不代表API的`task`键值。

`draft`阶段只校验结构，不用旧版时长/素材额度快照阻断计划。`submit`必须由当前用户请求明确授权具体job并给出预算上限；“跑总流程”、撰写提示词或模型选择都不自动授权生成。授权对象记录为`{authorized_by_user, job_ids, evidence, budget_limit:{amount,unit}}`，且`job_ids`与本次清单完全一致。校验器只能检查记录完整性，不能替代对话授权。

## 状态与证据

资产状态：`planned`（只有设定）、`candidate`（已生成未审）、`approved`（已看并可用）、`stale`（父版本或设定改变后失效）、`rejected`（不再用于生产）。生成任务：`planned → assets-ready → submitted → generated → reviewed`。状态转移必须有文件/任务/审片依据。生成任务的审核状态独立于资产“已生成”。

每条事实标`source_kind`：用户原文、项目定稿、官方文档、当前工具schema、实测观察或社区案例。记录`source_uri_or_path`与`checked_at`。社区观察可提示实验，不可单独解锁提交参数。文件存在或名称看起来正确不等于图像内容已核。

## 修改传播规则

人物身份/服装更改使该角色资产和使用它的镜头/提示词变旧；场景结构更改使相关区域、调度图和镜头构图变旧；单句措辞或语气变化只重验该语言单元所在镜头及上下文切点。标清失效范围，重生/重编译只覆盖确有影响的产物。

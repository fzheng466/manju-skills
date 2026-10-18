# 项目合同与记录

## 项目文件布局

完整项目使用可编辑的项目目录；未做的阶段不创建伪产物。

```text
project/
  project.json              项目、模型锁、台词、资产、任务和审核状态的机器可读真相源
  00_brief/brief.md          范围、风格、受众、预算和来源说明
  01_story/coverage.md       原文/事件覆盖与改编说明
  01_story/episode-01.md     冻结剧本
  02_assets/asset-ledger.csv 资产ID、版本、用途、路径和证据
  03_shots/shot-list.csv     镜头执行表
  04_prompts/job-*.md        Seedance所选版本的提示词正文（不含API载荷）
  05_media/{images,videos,audio}/ 实际返回文件
  06_edit/edit-plan.md       时间线、字幕、声音及转场计划
  07_qa/                     逐镜内容审核和技术报告
```

只做一条提示词时可以直接交付Markdown，不强制建立完整目录。项目清单保留原文件、通过资产和提示词的不可覆盖版本；路径相对`project.json`所在位置。

## 项目JSON契约

`project.json`顶层字段：

| 字段 | 规则 |
|---|---|
| `schema_version` | 当前合同版本，如`1.0` |
| `project_id`、`title` | 稳定项目ID与项目名 |
| `pipeline`、`model_profile` | `pipeline=seedance`；`model_profile`单项目固定为`seedance-2.0`或`seedance-2.5` |
| `aspect_ratio` | 固定`16:9` |
| `stage` | `draft`或`submit` |
| `generation_authorization` | 草稿记录为未授权；提交必须记录用户对精确job ID集合的明确授权、授权证据和非负预算上限/单位，不得由代理推断；job ID集合必须与本次提交清单完全一致 |
| `capability` | 草稿可为null；提交必须写当前服务核验记录：provider、精确model ID、核验时间、证据位置、16:9支持、已核验模式/输入角色/最短与最长时长；当前版本若有多模态参考还记录各类素材上限 |
| `utterances` | 按语言单元ID存完整原句、speaker、kind、language、tone；冻结后不改写 |
| `assets` | 资产ID、类型、状态、比例、版本、用途、来源、实际路径和哈希（若有） |
| `jobs` | 每个生成任务的model_profile、mode、duration、16:9、输入资产ID及用途、shots、提示词版本、剧集时间偏移 |

每个job含唯一`id`、与项目相同的`model_profile`、版本允许的`mode`、`duration_seconds`、`aspect_ratio=16:9`、`episode_start_seconds`、输入清单`inputs`、镜头`shots`、`prompt_version`和`compiled_prompt_path`。`inputs`使用`{asset_id, role}`；Seedance 2.0、2.5的role集合互斥，详见版本参考，不直接伪造平台槽位。`stage=submit`还需真实提示词正文路径和经核实的`request_record_path`。shot含稳定`id`、job内从0开始的`start_seconds/end_seconds`、`purpose`、单一`main_action`、`camera`、`start_state`、`end_state`、`continuity_from`（首镜可空）、`dialogue`列表及声音字段。shot应连续覆盖job时长，不得重叠/倒序/漏时。

`dialogue`每段写`utterance_id`、原文`text`、`speaker_id`和语气描述。全项目按`episode_start_seconds + shot.start_seconds`排序，同一语言单元分散在不同job/镜头中的片段拼接后必须逐字等于完整utterance。只有确实剪断的语句允许显式标记剪断；不要为了方便把旁白伪装成画内对白。

`mode`是本项目内部的制作模式，不等于API字段。2.0使用 `text_only / reference_image / multimodal_reference / frame_anchored` 中经过当前2.0接入核验的方案；2.5使用 `text_only / reference_set / first_last_frame` 中经过当前2.5接入核验的方案。项目校验器禁止跨版本模式。实际文件角色及限制详见对应版本参考；提交时必须符合当前Seedance服务与接入层证据。

`draft`阶段只校验结构，不用旧版能力快照阻断计划。`submit`必须由当前用户请求明确授权具体job并给出预算上限；“跑总流程”、撰写提示词或模型选择都不自动授权生成。授权对象记录为`{authorized_by_user, job_ids, evidence, budget_limit:{amount,unit}}`，且`job_ids`与本次清单完全一致。校验器只能检查记录完整性，不能替代对话授权。

## 状态与证据

资产状态：`planned`（只有设定）、`candidate`（已生成未审）、`approved`（已看并可用）、`stale`（父版本或设定改变后失效）、`rejected`（不再用于生产）。生成任务：`planned → assets-ready → submitted → generated → reviewed`。状态转移必须有文件/任务/审片依据。生成任务的审核状态独立于资产“已生成”。

每条事实标`source_kind`：用户原文、项目定稿、官方文档、当前工具schema、实测观察或社区案例。记录`source_uri_or_path`与`checked_at`。社区观察可提示实验，不可单独解锁提交参数。文件存在或名称看起来正确不等于图像内容已核。

## 修改传播规则

人物身份/服装更改使该角色资产和使用它的镜头/提示词变旧；场景结构更改使相关区域、调度图和镜头构图变旧；单句措辞或语气变化只重验该语言单元所在镜头及上下文切点。标清失效范围，重生/重编译只覆盖确有影响的产物。

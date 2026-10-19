# 失败模式库 v0

审片表 `category` 填 FM-ID。`applies_to` 可为 `h3` / `seedance` / `asset` / 渠道 ID。

| ID | 症状 | 根因层 | 最小修复 |
|---|---|---|---|
| FM-01 | 脸变圆、模板脸 | 资产提示词 | face-archetype 骨相几何，禁堆「瓜子脸」 |
| FM-02 | 隐藏人物提前露出 | 编译 | G5 出场守卫 + VIS_HIDDEN |
| FM-03 | 延长时首 1 秒跳帧 | 生成 | 首秒只写微动作 |
| FM-04 | 持物手左右漂移 | 导演谱/编译 | 末态句强制写左右手 |
| FM-05 | 特效遮住脸 | 编译 | 特效层级：脸前不放大特效 |
| FM-06 | 四视图背面左右镜像 | 资产 | 锁定句：以角色自身左右为准 |
| FM-07 | 流苏/飘带与身体或武器穿插 | 资产/生成 | 结构锚点：股数、起止点、间隙 |
| FM-08 | 战甲关节糊成一块 | 资产 | 分片叠压 + 活动缝隙 + 连接件 |
| FM-09 | 风格漂向写实真人 | 风格层 | cel / 国漫 CG 正向词 + 负向词 |
| FM-10 | H3 词汇照搬到 Seedance 后服饰细节丢失 | 风格层 | 双轨词表改写 |
| FM-11 | 特效漂：同一系统面板/法阵跨镜头剪影、颜色、边框光变化 | 资产/编译 | 出 `kind: fx` 16:9 模板，镜头 `<Picture n>` 只锁外形；`SHOT-FX-ASSET` |
| FM-12 | 特效糊脸：面板/法阵/刃光挡住面部 | 编译 | 面板在脸侧/胸前，面部前不放特效；`SHOT-FX-FACE` |
| FM-13 | 系统字镜像：背面视角反字或生成乱码长汉字 | 资产/后期 | 资产板无字；背面只露边框；`text_mode=baked_verified` 须先校对静帧，失败退回 `post_overlay` |
| FM-14 | 每镜重发明面板 | 编译 | 镜头词只写展开/流转/收束 + 时间码，外形引用 fx 资产 |
| FM-15 | 完整 UI 和中景人物同框，菜单看不清或人物被挤没 | 编译 | 未确认档位时用安全默认；确认 readable 后按 `fx_tier_confirmed`；全壳仍走插入镜；`SHOT-FX-UI` / `SHOT-FX-TIER` |
| FM-16 | 渠道能出声却输出后期配音 / 删对白 | 面谈/adapt | audio_output 渠道值优先；unknown 阻断；`SHOT-AUD-POST` |
| FM-17 | 同一角色跨镜换声 | 编译 | voice_profile 身份层逐字相同，只改表演层；`SHOT-AUD-VOICE` |
| FM-18 | 时长不在渠道枚举 | 面谈/adapt | duration.allowed + R-DUR-05 给出 pad/trim/split 选项，用户确认后回写 `duration_snapped_from`；`SHOT-DUR-ENUM` / `SHOT-DUR-ACK` / `SHOT-DUR-TC` |
| FM-19 | 2×2 场景整板进参考，模型发明结构/丢地标 | 绑定 | ref_role=scene_view 单格；`SHOT-REF-GRID` |
| FM-20 | 真人风控拒图 | 绑定/渠道 | realperson_policy；带脸合成静帧不进参考；`SHOT-REF-FACE` |
| FM-21 | 私有特效被非持有者看见/夹在对话中间 | 编译 | visibility=owner_only；`SHOT-FX-VIS` / `SHOT-FX-DIALOGUE` |
| FM-22 | 侧身/过肩时特效成墙 | 编译 | `SHOT-FX-BODY`：移到余光/缩小/收束 |
| FM-23 | 特效太小不炫 / 太大挤人 | look-dev | 档位 presence/readable/fullscreen + fx_tier_confirmed；`SHOT-FX-TIER` |
| FM-24 | 尾帧把上一镜特效带进下一镜 | 绑定 | `SHOT-REF-INHERIT` |
| FM-25 | 道具状态错（空碗/纱罩、门光乱闪） | 资产/编译 | prop_state + `SHOT-PROP-STATE` |
| FM-26 | 人与房间比例失真 | 资产/编译 | anchor_map 尺度锚 + `SHOT-SCALE-ROOM` |
| FM-27 | 审片声称台词已说出但未逐字核 | 审片 | 无 ASR/人工听写只记「口型时长相符，逐字未验收」 |

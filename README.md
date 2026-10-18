# 最新版本视频优化 skill（2026-10-18 Opus 优化安装）

用户说 **「使用我们最新的版本的skill」** 即走这里。

## 两个生产 skill

| 目录 | 模型 | 触发 |
|---|---|---|
| `skill-H3/` | MiniMax H3 全流程 | 走 H3、MiniMax、$minimax-h3-manju |
| `skill-SD/` | Seedance 2.0 与 2.5 | 走 Seedance、SD、$seedance-manju |

公共层在 `core/`（面谈、自适应拆段/裁图、G-CH 守卫、动漫 3D 词库、剧本工作室原文）。`build/vendor.py` 会把 `core/` 复制进各 skill 的 `_core/`。

## 调用时第一步

先问交付画幅（16:9 / 9:16 / 两条都要），再做渠道面谈 → 按交付线算生效能力 → 编译预览 → 你确认 → 才写提示词和资产图。详见 `core/references/channel/interview.md` 与 `core/references/assets/aspect-tracks.md`。

示例渠道档案：`examples/channels/proxy-a-h3.json`，复制到 `%USERPROFILE%\.manju\channels\`。

## 大纲能不能扩写

能。给大纲会走 P1 剧本（90–180 秒单集）→ P2 资产图（一句「开始生图」，一次一张）→ P3 分镜 → P4 编译。不是一键黑盒，每阶段要确认；生成要单独授权预算。

## 本版相对压缩包的改动

- 双 skill + core，不再把 H3/SD 当成三套互拷贝的包
- Seedance 2.5 无来源 30 秒/50 图数字降为待核验
- H3→SD 映射表与风格层（从导演谱转，不硬翻 H3 文本）
- 战甲/仙袍/流苏动漫 3D 示例提示词
- 渠道面谈与 10s/2 图等自适应规则
- 16:9 与 9:16 作为一等交付线：一条线渠道不支持时只暂停该线，不改另一条已定稿资产

Opus 原报告在：`D:\ai\逆向工程的开发教程\_3b_reverse\ai_drama_skill\_opus_answers\`

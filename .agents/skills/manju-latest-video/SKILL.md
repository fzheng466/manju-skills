---
name: manju-latest-video
description: "用户说「使用我们最新的版本的skill」「最新版本视频skill」「最新视频优化skill」「用最新 skill 做漫剧/短剧/H3/Seedance」时必须加载。路由到 D:\\最新版本视频优化skill 下的 skill-H3 或 skill-SD，第一步强制渠道面谈。"
---

# 最新版本视频优化 skill（路由）

本目录是触发入口。真正的流程在：

- `D:\最新版本视频优化skill\skill-H3\SKILL.md` — MiniMax H3
- `D:\最新版本视频优化skill\skill-SD\SKILL.md` — Seedance 2.0 / 2.5
- `D:\最新版本视频优化skill\core\` — 面谈、自适应规则、动漫/3D 资产词库、失败模式

## 一触发就做

1. 读本仓库 README。
2. 用户未指定模型时问一次：走 MiniMax H3 还是 Seedance 2.0/2.5。
3. 打开对应 skill 的 SKILL.md，**先做渠道面谈**（`core/references/channel/interview.md`），再扩写/资产/分镜/编译。
4. 不要用旧的独立 H3/Seedance 压缩包副本；以本路径为唯一最新版。

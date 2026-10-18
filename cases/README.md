# cases/ 实测案例库

真实生成结果、抽帧、花费只放本机 `$MANJU_HOME/cases/` 或本目录的 `local/`（已 gitignore）。仓库只保留模板和去密钥后的评分表。

每个案例一个子目录：`cases/<case-id>/`

```text
cases/
  README.md
  _template/
    SCORE.md
    director-notes.json
    h3-prompt.md
    sd-prompt.md
    request.redacted.json
  拾荒-ep001-sc001-巷口/     # 填实测后提交评分表，媒体不进 Git
```

## 最小实测集（Opus 建议的 3 镜）

| case-id | 类型 | 画幅 |
|---|---|---|
| dialogue | 文戏对白 | 16:9 或双轨 |
| action | 玄幻/系统异能动作 | 16:9 |
| portrait-two-shot | 9:16 双人纵深 | 9:16 |

## 评分表用法

复制 `_template/SCORE.md`，每项只填 pass / fail / n-a，并写证据（时间码或抽帧文件名）。失败项记 FM-ID。

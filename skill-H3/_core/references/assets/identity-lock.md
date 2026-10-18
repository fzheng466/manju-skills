# 角色身份锁（男女资产不得串套）

对标：Google Flow / Veo 类角色一致性流水线（角色卡先锁、参考图只绑该卡）。本仓库用字段锁，不靠模型“自己记得”。

## 强制字段

每个人物：

```json
{
  "character_id": "SHEN_YAN",
  "name": "沈砚",
  "presentation_sex": "male"
}
```

每件服装 / 武器 / 道具：

```json
{
  "asset_id": "WPN_SHEN_HALBERD",
  "kind": "weapon",
  "owner_id": "SHEN_YAN",
  "presentation_sex": "male"
}
```

`owner_id` 必须指向一个已声明角色。没有主人的剧情道具先建 `owner_id`，禁止“公共女装板给男主穿”。

## 生图前

```text
python -m core.lib.asset_prompt --kind character --aspect 16:9 --sex male --character-id SHEN_YAN --file shen.md
python -m core.lib.identity --project project.json
python -m core.lib.identity --prompt shen.md --sex male --character-id SHEN_YAN
```

男角色提示词出现抹胸/步摇/细跟/丝袜等女装码，或女角色出现喉结/胸肌/胡茬，直接 FAIL。

角色卡应带 `signature` / `identification_points`（或从【识别点】【服装】抽取）。刘桂芳板上出现陈汉的「橄榄绿夹克 / 胶布眼镜」报 `ID-SIG`。`python -m core.lib.asset_prompt ... --project project.json` 才会跑这张表。

## 视频编译

submit 时 `validate_project.py` 会跑身份检查：镜头不得把 A 的服装绑到 B 身上。

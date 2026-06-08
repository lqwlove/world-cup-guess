# football-data.org 数据概览同步

将 [football-data.org](https://www.football-data.org/) v4 API 的结构化数据写入 `match_facts`，供 **数据概览** Tab 与 AI 合议引用。

## 1. 获取 API Key

1. 注册并登录 https://www.football-data.org/
2. 在控制台复制 Token
3. 写入 `.env.production`（或本地 `.env`）：

```env
FOOTBALL_DATA_API_KEY=你的token
FOOTBALL_DATA_COMPETITION=WC
FOOTBALL_DATA_BASE_URL=https://api.football-data.org/v4
```

免费套餐有请求频率限制，全量同步 104 场时请避免短时间内重复执行。

## 2. 同步命令

```bash
# 全量（已导入赛程、非占位队名的场次）
./start.sh sync-facts

# 单场
./start.sh sync-facts -- --match-id fifa-400021443
```

或在 `services/api` 目录：

```bash
conda activate wcguess
python -m app.scripts.sync_football_facts --match-id fifa-400021443
```

## 3. 写入的事实类型

| fact_type | 说明 |
|-----------|------|
| `recent_form` | 主/客队近 5 场战绩与进失球 |
| `head_to_head` | 历史交锋（需 API 能按日期匹配到该场） |
| `standing` | 小组赛积分榜行（淘汰赛阶段可能为空） |

`source` 均为 `football-data.org`；重复同步会先删除该场旧 API 事实再写入。

## 4. 队名映射

中文队名通过 `seeds/football_data_team_map.json` 映射到 API 英文队名（与 FIFA 导入脚本一致）。若某场同步为 0 条，请检查：

- 是否为占位队名（含「组」「胜者」等）
- 映射表中是否有该中文队名
- football-data 是否已发布该届世界杯赛程数据

## 5. HTTP API（可选）

```bash
curl -X POST http://127.0.0.1:8000/api/matches/fifa-400021443/facts/sync
```

## 6. 验证

```bash
curl -s http://127.0.0.1:8000/api/matches/fifa-400021443/facts | jq '.facts | length'
```

前端打开该场 **数据概览** Tab 即可查看。

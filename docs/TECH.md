# 技术架构说明

## 栈

- **前端**: Next.js 15 + Tailwind (`apps/web`)
- **API**: FastAPI + SQLModel (`services/api`)
- **合议引擎**: LangGraph 状态机 (`app/deliberation/graph.py`)
- **异步**: ARQ + Redis
- **数据库**: PostgreSQL 16

## 本地启动

```bash
cp .env.example .env
make up
```

- Web: http://localhost:3000
- API: http://localhost:8000/docs

## 生产部署（腾讯云 CVM）

见 [DEPLOY.md](./DEPLOY.md)。使用 `docker-compose.prod.yml` + `.env.production`，Nginx 在宿主机配置。

## 关键路径

| 能力 | 入口 |
|------|------|
| 赛程列表 | `GET /api/matches` |
| 触发合议 | `POST /api/matches/{id}/discussions` |
| SSE 流 | `GET /api/discussions/{id}/stream` |
| 共识结果 | `GET /api/matches/{id}/consensus` |

## 合议阶段

Opening → CrossExam → DeepDive → PlaybookSplit → FinalVote → Consensus

`max_rounds=30` 未达成则 `PARTIAL_CONSENSUS`。

## 环境变量

见根目录 `.env.example`。开发默认 `MOCK_LLM=true`，无需 API Key 即可跑通合议。

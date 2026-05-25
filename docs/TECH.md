# 技术架构说明

## 栈

- **前端**: Next.js 15 + Tailwind (`apps/web`)
- **API**: FastAPI + SQLModel (`services/api`)
- **合议引擎**: LangGraph 状态机 (`app/deliberation/graph.py`)
- **异步**: ARQ + Redis
- **数据库**: PostgreSQL
- **运行**: Conda（Python 3.12）+ Node.js；生产见 [DEPLOY.md](./DEPLOY.md)

## 本地开发

```bash
cd services/api && conda activate wcguess && uvicorn app.main:app --reload
cd apps/web && npm run dev
```

## 关键 API

| 能力 | 入口 |
|------|------|
| 赛程列表 | `GET /api/matches` |
| 触发合议 | `POST /api/matches/{id}/discussions` |
| SSE 流 | `GET /api/discussions/{id}/stream` |
| 共识结果 | `GET /api/matches/{id}/consensus` |

## 环境变量

开发：`.env.example`  
生产：`.env.production.example`

### 大模型（OpenAI 兼容）

| 变量 | 说明 |
|------|------|
| `MOCK_LLM` | `true` 时用本地模板，不调 API |
| `LLM_PROVIDER` | `deepseek` / `volcengine` / `openai` / `anthropic` |
| `LLM_MODEL` | 模型名；火山方舟填**推理接入点 ID**（如 `ep-xxx`） |
| `OPENAI_API_KEY` | DeepSeek / 火山 / OpenAI 共用 |
| `OPENAI_API_BASE` | 可选，覆盖默认 API 地址 |

DeepSeek 与火山引擎均走 `langchain-openai` + 自定义 `base_url`，无需改业务代码。

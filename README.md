# 世界杯智能预测平台

AI 战术室合议：多角色充分讨论，输出胜平负 / 比分 / 让球推荐，并对照预测市场 Edge。

- 产品需求：[docs/PRD.md](docs/PRD.md)
- 技术说明：[docs/TECH.md](docs/TECH.md)

## 快速开始

```bash
cp .env.example .env
docker compose up --build
```

访问 http://localhost:3000 — 推荐先看决赛场次 `wc2026-final`（已预置演示合议）。

## 项目结构

```
apps/web/          # Next.js 前端
services/api/      # FastAPI + LangGraph + ARQ
seeds/             # 赛程、事实、市场映射种子数据
```

## 开发

```bash
# API 单测
cd services/api && pip install -r requirements.txt && pytest

# 本地 API（需 Postgres + Redis）
uvicorn app.main:app --reload
```
# world-cup-guess

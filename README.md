# 世界杯智能预测平台

AI 战术室合议：多角色充分讨论，输出胜平负 / 比分 / 让球推荐，并对照预测市场 Edge。

- 产品需求：[docs/PRD.md](docs/PRD.md)
- 技术说明：[docs/TECH.md](docs/TECH.md)

## 快速开始（本地开发）

```bash
cp .env.example .env
docker compose up --build
```

访问 http://localhost:3000 — 推荐先看决赛场次 `wc2026-final`（已预置演示合议）。

## 服务器部署

见 [docs/DEPLOY.md](docs/DEPLOY.md)。Postgres / Redis 用宿主机实例，Compose 只跑 api、worker、web；Nginx 自行配置（示例端口 8081）。

```bash
cp .env.production.example .env.production
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

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

# 世界杯智能预测平台

AI 战术室合议：多角色充分讨论，输出胜平负 / 比分 / 让球推荐，并对照预测市场 Edge。

- 产品需求：[docs/PRD.md](docs/PRD.md)
- 技术说明：[docs/TECH.md](docs/TECH.md)
- **服务器部署**：[docs/DEPLOY.md](docs/DEPLOY.md)

## 本地开发

需本机 PostgreSQL、Redis，或使用自己的连接串。

```bash
cp .env.example .env
# 编辑 DATABASE_URL、REDIS_URL

cd services/api
conda create -n wcguess python=3.12 -y && conda activate wcguess
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed

uvicorn app.main:app --reload --port 8000
# 另开终端: arq app.workers.settings.WorkerSettings

cd apps/web
npm install
npm run dev
```

访问 http://localhost:3000

## 服务器（Conda）

```bash
cp .env.production.example .env.production
chmod +x start.sh && ./start.sh start
```

见 [docs/DEPLOY.md](docs/DEPLOY.md)：`./start.sh stop` / `status` / `build-web`

## 项目结构

```
apps/web/          # Next.js 前端
services/api/      # FastAPI + LangGraph + ARQ
seeds/             # 赛程、事实、市场映射
```

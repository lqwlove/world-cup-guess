# 服务器部署（Docker Compose）

- **PostgreSQL**：宿主机已有（示例端口 `55443`，库 `ai_db`）
- **Redis**：Compose 容器
- **Nginx**：自行配置

## 1. 数据库连接

宿主机上（本机调试）：

```env
postgresql+psycopg://postgresql:密码@localhost:55443/ai_db
```

**Docker 容器内**写入 `.env.production` 时须改两处：

| 项目 | 宿主机 | 容器内 |
|------|--------|--------|
| 主机 | `localhost` | `host.docker.internal` |
| API 驱动 | `+psycopg` 等 | `+asyncpg`（本项目 FastAPI 使用） |

```env
DATABASE_URL=postgresql+asyncpg://postgresql:密码@host.docker.internal:55443/ai_db
DATABASE_URL_SYNC=postgresql://postgresql:密码@host.docker.internal:55443/ai_db
```

`pg_hba.conf` 需允许 Docker 网段访问（如 `172.16.0.0/12`），Postgres 需监听对应地址；改后 `reload postgresql`。

## 2. 启动

```bash
cp .env.production.example .env.production
vim .env.production   # 填入真实密码、NEXT_PUBLIC_API_URL、CORS_ORIGINS

docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

种子数据（可选，首次）：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec api python -m app.scripts.seed
```

```bash
curl http://127.0.0.1:8000/health
```

## 3. 常用命令

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api worker web
```

## 4. Nginx

- `/` → `127.0.0.1:3000`
- `/api/` → `127.0.0.1:8000`
- SSE：`proxy_buffering off`，`proxy_read_timeout` ≥ 3600s

# 服务器部署（Docker Compose）

- **PostgreSQL**：宿主机 `55443`，库 `ai_db`
- **Redis**：宿主机 `7740`
- **Docker**：仅跑 `api`、`worker`、`web`（映射本机 3000 / 8000）
- **Nginx**：HTTP `8081`，自行配置

## 1. 环境变量（`.env.production`）

宿主机本机调试：

```env
DATABASE_URL=postgresql+psycopg://postgresql:密码@localhost:55443/ai_db
REDIS_URL=redis://localhost:7740/0
```

**Docker 容器内**须把 `localhost` 改为 `host.docker.internal`：

```env
DATABASE_URL=postgresql+asyncpg://postgresql:密码@host.docker.internal:55443/ai_db
DATABASE_URL_SYNC=postgresql://postgresql:密码@host.docker.internal:55443/ai_db
REDIS_URL=redis://host.docker.internal:7740/0

NEXT_PUBLIC_API_URL=http://公网IP:8081
CORS_ORIGINS=http://公网IP:8081
```

确保 Postgres / Redis 允许 Docker 网段连接；Redis `bind` 需包含可被容器访问的地址。

## 2. 启动

```bash
cp .env.production.example .env.production
vim .env.production

docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

种子数据（可选）：

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

## 4. Nginx（8081）

见 [deploy/nginx.example.conf](../deploy/nginx.example.conf)。安全组放行 **8081**，勿对公网开放 3000、8000、55443、7740。

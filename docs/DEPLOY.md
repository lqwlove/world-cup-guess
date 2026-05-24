# 服务器部署（Conda + Nginx）

## 1. 环境变量

```bash
cp .env.production.example .env.production
vim .env.production
```

```env
DATABASE_URL=postgresql+asyncpg://postgresql:密码@localhost:55443/ai_db
DATABASE_URL_SYNC=postgresql://postgresql:密码@localhost:55443/ai_db
REDIS_URL=redis://localhost:7740/0
NEXT_PUBLIC_API_URL=http://公网IP:8081
CORS_ORIGINS=http://公网IP:8081
```

首次需创建 Conda 环境：

```bash
cd services/api
conda env create -f environment.yml   # 或 conda create -n wcguess python=3.12 && pip install -r requirements.txt
```

## 2. 一键启动

```bash
chmod +x start.sh
./start.sh start       # 数据库迁移 + 启动 api / worker / web
./start.sh status
./start.sh stop
./start.sh restart
./start.sh seed        # 首次导入赛程（可选）
./start.sh build-web   # 改了 NEXT_PUBLIC_API_URL 后重建前端
```

- 日志：`logs/api.log`、`logs/worker.log`、`logs/web.log`
- 进程 pid：`.run/`
- 默认 Conda 环境名 `wcguess`，可 `CONDA_ENV=xxx ./start.sh start`

## 3. Nginx

[deploy/nginx.example.conf](../deploy/nginx.example.conf) — 对外 **8081**，反代本机 `3000` / `8000`。

## 4. 自检

```bash
curl http://127.0.0.1:8000/health
curl -I http://127.0.0.1:3000
curl http://127.0.0.1:8081/health
```

## 5. 更新代码

```bash
git pull
cd services/api && conda activate wcguess && pip install -r requirements.txt
./start.sh build-web    # 若前端有变
./start.sh restart
```

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

首次创建 Conda 环境（也可由 `start` 自动创建）：

```bash
./start.sh setup
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

## 3. 前端必须先构建再启动

`/_next/static/*.css|*.js` **不会**单独出现在网站根目录，而是由 **`npm run build` + `npm run start`（端口 3000）** 提供。

```bash
# .env.production 里写好 NEXT_PUBLIC_API_URL=http://公网IP:8081
./start.sh build-web    # 或 ./start.sh start（会自动 build）
./start.sh start        # 会起 api + worker + web(3000)
```

自检（在服务器上）：

```bash
curl -I http://127.0.0.1:3000/_next/static/css/   # 应 200 或 404 目录；具体文件用浏览器里完整路径测
curl -I http://127.0.0.1:3000/
```

若本机 3000 正常、外网 8081 仍 404 → 见下方宝塔 Nginx。

## 4. Nginx / 宝塔

[deploy/nginx.example.conf](../deploy/nginx.example.conf) — 对外 **8081**。

**必须**反代到本机进程，不能只配「网站根目录」：

| 路径      | 反代到                                  |
| --------- | --------------------------------------- |
| `/`       | `http://127.0.0.1:3000`                 |
| `/_next/` | `http://127.0.0.1:3000`（**缺一不可**） |
| `/api/`   | `http://127.0.0.1:8000`                 |

宝塔 → 站点 → **配置文件**：确认有 `location /_next/` 和 `location /` 的 `proxy_pass`，且未让静态根目录抢先返回 404。

## 5. 自检

```bash
curl http://127.0.0.1:8000/health
curl -I http://127.0.0.1:3000
curl http://127.0.0.1:8081/health
```

## 6. 更新代码

```bash
git pull
cd services/api && conda activate wcguess && pip install -r requirements.txt
./start.sh build-web    # 若前端有变
./start.sh restart
```

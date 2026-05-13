# CAIWU 容器化部署方案

## 架构

```
服务器 117.50.145.93
/data/service/
├── docker-compose.yml          # 编排 4 服务
├── .env.prod                   # 生产环境变量
├── backend/                    # 代码目录（Dockerfile 挂载）
│   ├── app/                    # FastAPI 应用代码
│   ├── requirements.txt        # Python 依赖
│   └── Dockerfile              # python:3.11-slim + uvicorn
├── frontend/                   # 前端目录
│   ├── dist/                   # vite build 产物
│   ├── nginx.conf              # nginx 配置
│   └── Dockerfile              # nginx:alpine
└── data/                       # 持久化数据
    ├── postgres/               # PG 数据卷
    ├── redis/                  # Redis 数据卷
    └── reports/                # 报告输出
```

## 服务清单

| 服务 | 容器名 | 端口映射 | 说明 |
|------|--------|---------|------|
| postgres | caiwu-postgres | 5432:5432 | PostgreSQL 15，持久化到 data/postgres |
| redis | caiwu-redis | 6379:6379 | Redis 7 AOF，持久化到 data/redis |
| backend | caiwu-backend | 8000:8000 | FastAPI + uvicorn，代码挂载 |
| frontend | caiwu-frontend | 80:80 | Nginx 静态文件 + API 反向代理 |

## 部署步骤

### 1. 前端构建（本地）

```bash
cd frontend && npm run build
```

产物输出到 `frontend/dist/`。

### 2. 创建部署文件（已完成）

- `backend/Dockerfile` — python:3.11-slim 基础镜像，安装 requirements.txt
- `frontend/Dockerfile` — nginx:alpine，COPY dist + nginx.conf
- `frontend/nginx.conf` — 静态文件服务 + `/api/v1/` → backend:8000 反向代理
- `deploy/docker-compose.yml` — 4 服务编排 + healthcheck
- `deploy/.env.prod` — 生产环境变量（DB_HOST=postgres, REDIS_HOST=redis）

### 3. SSH 部署到服务器

执行 `deploy/deploy.sh` 脚本：
1. SSH 到服务器创建目录结构
2. 上传 docker-compose.yml + .env.prod
3. 上传后端代码
4. 上传前端 dist + nginx.conf
5. 执行 `docker compose up -d --build`
6. 执行数据库表创建迁移（基于 SQLAlchemy 模型 create_all）
7. 验证健康检查

### 4. 验证

```
curl http://117.50.145.93/health          # 前端（通过 nginx）
curl http://117.50.145.93:8000/health     # 后端直接访问
```

## 数据迁移策略

目标服务器使用本地 PG + Redis，数据需要从零创建。
- PG: 新实例，使用 `create_all()` 基于模型创建表结构
- Redis: 新实例，无历史数据
- 如需导入历史数据，后续通过 Excel 上传功能

## 常用运维命令

```bash
# 查看日志
ssh ubuntu@117.50.145.93 "sudo docker compose -f /data/service/docker-compose.yml logs -f"

# 重启单个服务
ssh ubuntu@117.50.145.93 "sudo docker compose -f /data/service/docker-compose.yml restart backend"

# 重新构建并启动
ssh ubuntu@117.50.145.93 "sudo docker compose -f /data/service/docker-compose.yml up -d --build"

# 停止所有服务
ssh ubuntu@117.50.145.93 "sudo docker compose -f /data/service/docker-compose.yml down"

# 进入后端容器
ssh ubuntu@117.50.145.93 "sudo docker exec -it caiwu-backend bash"

# 查看数据库连接
ssh ubuntu@117.50.145.93 "sudo docker exec caiwu-postgres psql -U learnhouse -d caiwu -c '\dt'"
```

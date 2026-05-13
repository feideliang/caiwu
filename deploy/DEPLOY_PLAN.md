# 服务器部署方案：同步更新到 117.50.145.93

## Context

代码已提交到 GitHub（feideliang/caiwu.git），需要部署到远程服务器 ubuntu@117.50.145.93。
现有 deploy.sh 脚本已处理大部分流程，但有几个关键缺失需要补齐。

---

## 部署前修复清单

| # | 问题 | 修复 |
|---|------|------|
| 1 | docker-compose.yml 缺 celery worker + beat | 加 celery-worker 和 celery-beat 服务 |
| 2 | .env.prod 缺 BI_MYSQL_* 配置 | 加 BI_MYSQL_HOST/PORT/DATABASE/USER/PASSWORD |
| 3 | JWT_SECRET 是默认占位符 | 生成随机密钥替换 |

---

## 部署步骤

1. **修复 docker-compose.yml** — 加 celery worker/beat 两个服务（复用 backend image）
2. **修复 .env.prod** — 加 BI_MYSQL_* 和换 JWT_SECRET
3. **构建前端** — `cd frontend && npm run build`
4. **执行 deploy.sh** — 自动 SSH 上传 + docker compose up
5. **验证** — curl 健康检查端点 + 检查 docker compose ps

---

## 关键文件

- `deploy/docker-compose.yml` — 加 celery 服务
- `deploy/.env.prod` — 加 BI_MYSQL + JWT_SECRET
- `deploy/deploy.sh` — 不需改动，原有脚本可正常执行
- `frontend/Dockerfile` + `frontend/nginx.conf` — 不需改动
- `backend/Dockerfile` — 不需改动

## Celery 服务定义

```yaml
celery-worker:
  build: { context: ./backend, dockerfile: Dockerfile }
  container_name: caiwu-celery-worker
  env_file: .env.prod
  command: celery -A app.celery_app worker --loglevel=info --concurrency=2
  volumes: [./backend:/app, ./data/reports:/app/output/reports]
  depends_on: [redis: condition: service_healthy]

celery-beat:
  build: { context: ./backend, dockerfile: Dockerfile }
  container_name: caiwu-celery-beat
  env_file: .env.prod
  command: celery -A app.celery_app beat --loglevel=info
  volumes: [./backend:/app]
  depends_on: [redis: condition: service_healthy]
```

## 验证

```bash
# 健康检查
curl http://117.50.145.93/health
curl http://117.50.145.93/api/v1/health

# Docker 状态
ssh ubuntu@117.50.145.93 'cd /data/service && docker compose ps'

# 日志
ssh ubuntu@117.50.145.93 'cd /data/service && docker compose logs -f backend'
```
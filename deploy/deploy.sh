#!/usr/bin/env bash
set -euo pipefail

echo "=== CAIWU Deployment Script ==="
echo "Target: /data/service on 117.50.145.93"
echo ""

REMOTE="ubuntu@117.50.145.93"
TARGET_DIR="/data/service"

# Step 1: Create target directory on remote server
echo "[1/7] Creating remote directory structure..."
ssh "$REMOTE" "sudo mkdir -p $TARGET_DIR/data/postgres $TARGET_DIR/data/redis $TARGET_DIR/data/reports"

# Step 2: Upload docker-compose.yml and env
echo "[2/7] Uploading docker-compose.yml and .env.prod..."
scp docker-compose.yml .env.prod "$REMOTE:$TARGET_DIR/"

# Step 3: Upload backend code
echo "[3/7] Uploading backend code..."
scp -r ../backend "$REMOTE:$TARGET_DIR/"

# Step 4: Upload frontend dist and nginx config
echo "[4/7] Uploading frontend dist + nginx.conf..."
ssh "$REMOTE" "mkdir -p $TARGET_DIR/frontend/dist"
scp -r ../frontend/dist/* "$REMOTE:$TARGET_DIR/frontend/dist/"
scp ../frontend/nginx.conf "$REMOTE:$TARGET_DIR/frontend/"
scp ../frontend/Dockerfile "$REMOTE:$TARGET_DIR/frontend/"

# Step 5: SSH into server and deploy
echo "[5/7] Building and starting containers..."
ssh "$REMOTE" "sudo bash -s" << 'REMOTE_SCRIPT'
set -euo pipefail
cd /data/service

# Install docker compose plugin if not present
if ! docker compose version > /dev/null 2>&1; then
    echo "Installing Docker Compose..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-compose-plugin
fi

# Stop existing containers if any
docker compose down 2>/dev/null || true

# Build and start
docker compose up -d --build

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 15

# Check health
docker compose ps
REMOTE_SCRIPT

# Step 6: Run database migration
echo "[6/7] Running database migration..."
ssh "$REMOTE" "sudo docker exec caiwu-backend python -c \"
import asyncio
from app.db.session import engine
from sqlalchemy.ext.automap import automap_base
async def run():
    async with engine.begin() as conn:
        # Create all tables from models
        from app.models.core import FinancialData
        from app.models.v3 import PredictionResult, ReportTask
        await conn.run_sync(type(engine).sync_engine.metadata.create_all)
        print('Tables created successfully')
asyncio.run(run())
\" 2>&1 || echo 'Migration: some tables may already exist'"

# Step 7: Verify deployment
echo "[7/7] Verifying deployment..."
sleep 5
HEALTH=$(ssh "$REMOTE" "curl -s http://localhost:80/health || curl -s http://localhost:8000/health" 2>/dev/null || echo "unreachable")
echo "Health check: $HEALTH"

echo ""
echo "=== Deployment Complete ==="
echo "Frontend: http://117.50.145.93"
echo "Backend API: http://117.50.145.93/api/v1/health"
echo "Backend direct: http://117.50.145.93:8000"
echo ""
echo "Check logs:"
echo "  ssh ubuntu@117.50.145.93 'sudo docker compose -f /data/service/docker-compose.yml logs -f'"

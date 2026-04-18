#!/bin/bash
# =============================================================
# deploy.sh — Deploy wan-animate to VPS from Termux via SSH
# Usage: bash deploy.sh
# =============================================================

set -e

# ---- EDIT THESE ----
VPS_USER="your_username"
VPS_HOST="your.vps.ip.or.domain"
VPS_PORT="22"
DEPLOY_DIR="/opt/wan-animate"
# --------------------

echo "🚀 Deploying wan-animate to $VPS_HOST..."

# 1. Create deploy dir on VPS
ssh -p $VPS_PORT ${VPS_USER}@${VPS_HOST} "mkdir -p ${DEPLOY_DIR}"

# 2. Copy all project files
scp -P $VPS_PORT -r \
  backend \
  frontend \
  Dockerfile \
  docker-compose.yml \
  .env.example \
  ${VPS_USER}@${VPS_HOST}:${DEPLOY_DIR}/

# 3. Deploy on VPS
ssh -p $VPS_PORT ${VPS_USER}@${VPS_HOST} << 'REMOTE'
cd /opt/wan-animate

# Create .env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  Created .env from template — edit FAL_KEY if needed (optional)"
fi

# Pull latest or build
docker compose down --remove-orphans 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

echo ""
echo "✅ Container status:"
docker compose ps

echo ""
echo "📋 Logs (last 20 lines):"
docker compose logs --tail=20
REMOTE

echo ""
echo "✅ Deployment complete!"
echo "🌐 App running at: http://${VPS_HOST}:8000"

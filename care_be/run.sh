#!/bin/bash
# CARE Lightweight Backend — Quick Start
# No Docker, no Postgres, no Redis, no Celery, no MinIO required.

set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║   CARE Lightweight Backend — Starting...             ║"
echo "╚══════════════════════════════════════════════════════╝"

# Setup virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# Load environment variables from .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

export HF_TOKEN="${HF_TOKEN:-}" # Token should be provided via environment variable, do not hardcode

# Install dependencies
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt

echo ""
echo "✅ Dependencies installed"
echo "🚀 Starting server on http://localhost:9000"
echo "📖 API docs at http://localhost:9000/docs"
echo ""
echo "Default credentials:"
echo "  admin / admin"
echo "  dr-shivani / Coronasafe@123"
echo ""

# Start uvicorn
uvicorn main:app --host 0.0.0.0 --port 9000 --reload

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3.13 >/dev/null || { echo "Install Python 3.13 first."; exit 1; }
command -v npm >/dev/null || { echo "Load nvm or install Node.js first."; exit 1; }
command -v initdb >/dev/null || { echo "Install PostgreSQL 17 first."; exit 1; }
python3.13 -m venv .venv313
.venv313/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm exec --yes --package=npm@11 -- npm ci --no-audit --no-fund && npm run build)
echo "Installed. Start with: python3.13 personal/manage.py start"

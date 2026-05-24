#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/ai-police-sim}"
BACKEND_DIR="$PROJECT_DIR/backend"

cd "$BACKEND_DIR"

python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env created from .env.example — edit secrets before production use."
fi

./venv/bin/python init_db.py

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  if ! python3 -m venv .venv 2>/tmp/phishing_venv_error.log; then
    cat /tmp/phishing_venv_error.log
    echo
    echo "Missing prerequisite: python3 venv support is not installed."
    echo "Install your system package for venv support, then run ./run.sh again."
    exit 1
  fi
fi

source .venv/bin/activate
python3 -m ensurepip --upgrade >/dev/null 2>&1 || true
python3 -m pip install -r requirements.txt
exec uvicorn app.main:app --reload --host 127.0.0.1 --port 7777 --log-level info

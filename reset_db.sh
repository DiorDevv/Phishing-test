#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="$ROOT_DIR/data/simulator.db"

if [[ -f "$DB_PATH" ]]; then
  rm "$DB_PATH"
fi

echo "Database reset: $DB_PATH"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Create it first with: python3.12 -m venv .venv"
  exit 1
fi

source .venv/bin/activate
exec python -m odoo -c odoo.conf --logfile=


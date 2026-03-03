#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/compose.yaml"
ENV_FILE="$ROOT_DIR/deploy/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

echo "This will stop and remove containers and volumes (all data removed)."
read -r -p "Type YES to continue: " ans
if [[ "$ans" != "YES" ]]; then
  echo "Cancelled"
  exit 0
fi

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v --remove-orphans
echo "Uninstall completed."

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

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

echo
echo "Container health:"
for c in wms_db wms_app; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    docker inspect --format "$c => {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}" "$c"
  else
    echo "$c => not running"
  fi
done

echo
echo "Recent logs (wms_app, last 60 lines):"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs --tail 60 odoo || true

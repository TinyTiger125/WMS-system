#!/usr/bin/env bash
set -euo pipefail

: "${ODOO_HTTP_PORT:=8069}"
curl -fsS "http://127.0.0.1:${ODOO_HTTP_PORT}/web/login" >/dev/null

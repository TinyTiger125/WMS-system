#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_USER=""
REMOTE_HOST=""
REMOTE_DIR="/home/neo/WMS-system"
SSH_PASSWORD="${WMS_SSH_PASSWORD:-}"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/verify_remote_consistency.sh --user neo --host 100.122.169.32 [--remote-dir /home/neo/WMS-system] [--password xxx]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) REMOTE_USER="$2"; shift 2 ;;
    --host) REMOTE_HOST="$2"; shift 2 ;;
    --remote-dir) REMOTE_DIR="$2"; shift 2 ;;
    --password) SSH_PASSWORD="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

[[ -n "$REMOTE_USER" && -n "$REMOTE_HOST" ]] || { usage; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }; }
need_cmd shasum
need_cmd scp
need_cmd ssh
if [[ -n "$SSH_PASSWORD" ]]; then need_cmd expect; fi

ssh_run() {
  local remote_cmd="$1"
  if [[ -n "$SSH_PASSWORD" ]]; then
    expect <<EOF
set timeout 180
spawn ssh ${REMOTE_USER}@${REMOTE_HOST} {${remote_cmd}}
expect {
  "*yes/no*" { send "yes\r"; exp_continue }
  "*password:*" { send "${SSH_PASSWORD}\r" }
}
expect eof
EOF
  else
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "${remote_cmd}"
  fi
}

scp_put() {
  local local_file="$1"
  local remote_path="$2"
  if [[ -n "$SSH_PASSWORD" ]]; then
    expect <<EOF
set timeout 180
spawn scp ${local_file} ${REMOTE_USER}@${REMOTE_HOST}:${remote_path}
expect {
  "*yes/no*" { send "yes\r"; exp_continue }
  "*password:*" { send "${SSH_PASSWORD}\r" }
}
expect eof
EOF
  else
    scp "${local_file}" "${REMOTE_USER}@${REMOTE_HOST}:${remote_path}"
  fi
}

LOCAL_SUM="/tmp/local_consistency_sha256.txt"
(cd "$ROOT_DIR" && \
  find custom deploy installer doc -type f \
    ! -name '._*' ! -name '.DS_Store' ! -name '*.pyc' ! -path '*/__pycache__/*' \
    -print0 | sort -z | xargs -0 shasum -a 256 > "$LOCAL_SUM")

scp_put "$LOCAL_SUM" "~/local_consistency_sha256.txt"

ssh_run "
set -e
cd ${REMOTE_DIR}
find custom deploy installer doc -type f -name '._*' -delete || true
find custom deploy installer doc -type f ! -name '._*' ! -name '.DS_Store' ! -name '*.pyc' ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum > /tmp/remote_consistency_sha256.txt
comm -13 <(sort ~/local_consistency_sha256.txt) <(sort /tmp/remote_consistency_sha256.txt) | grep -v ' deploy/.env$' > /tmp/remote_only.txt || true
comm -23 <(sort ~/local_consistency_sha256.txt) <(sort /tmp/remote_consistency_sha256.txt) > /tmp/local_only.txt || true
find custom/addons -type f ! -name '._*' ! -name '*.pyc' ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum > /tmp/host_custom_sha.txt
docker exec wms_app bash -lc \"cd /mnt/extra-addons && find . -type f ! -name '*.pyc' ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum\" | sed 's|  \\./|  custom/addons/|' > /tmp/container_custom_sha.txt
comm -3 <(sort /tmp/host_custom_sha.txt) <(sort /tmp/container_custom_sha.txt) > /tmp/host_container_diff.txt || true
echo 'remote_only_count='\"\$(wc -l < /tmp/remote_only.txt)\"
echo 'local_only_count='\"\$(wc -l < /tmp/local_only.txt)\"
echo 'host_container_diff_count='\"\$(wc -l < /tmp/host_container_diff.txt)\"
if [[ -s /tmp/remote_only.txt || -s /tmp/local_only.txt || -s /tmp/host_container_diff.txt ]]; then
  echo '---remote_only---'; sed -n '1,40p' /tmp/remote_only.txt
  echo '---local_only---'; sed -n '1,40p' /tmp/local_only.txt
  echo '---host_container_diff---'; sed -n '1,40p' /tmp/host_container_diff.txt
  exit 2
fi
echo 'CONSISTENCY_CHECK=PASS'
"

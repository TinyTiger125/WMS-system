#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/deploy/compose.yaml"
ENV_EXAMPLE="$ROOT_DIR/deploy/.env.example"
ENV_FILE="$ROOT_DIR/deploy/.env"

APP_CONTAINER="wms_app"
DB_CONTAINER="wms_db"

MIN_MEM_GB="4"
MIN_DISK_GB="20"
WAIT_TIMEOUT_SEC="600"

log() { printf "[INFO] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
fail() { printf "[ERROR] %s\n" "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

os_id=""
os_like=""
load_os_info() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    os_id="${ID:-}"
    os_like="${ID_LIKE:-}"
  fi
}

require_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  command -v sudo >/dev/null 2>&1 || fail "This installer needs root privilege (sudo not found)."
  sudo -n true >/dev/null 2>&1 || fail "Please run with a sudo-enabled user."
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 18 | tr -d '\n' | tr '/+' 'AB'
  else
    date +%s | sha256sum | cut -c1-24
  fi
}

check_system_requirements() {
  local arch
  arch="$(uname -m)"
  case "$arch" in
    x86_64|aarch64|arm64) ;;
    *) warn "Unverified architecture: $arch" ;;
  esac

  need_cmd awk
  need_cmd sed
  need_cmd grep
  need_cmd curl

  local mem_kb mem_gb disk_kb disk_gb
  mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
  mem_gb=$((mem_kb / 1024 / 1024))
  if (( mem_gb < MIN_MEM_GB )); then
    warn "Memory ${mem_gb}GB is below recommended ${MIN_MEM_GB}GB"
  fi

  disk_kb="$(df -Pk "$ROOT_DIR" | awk 'NR==2 {print $4}')"
  disk_gb=$((disk_kb / 1024 / 1024))
  if (( disk_gb < MIN_DISK_GB )); then
    warn "Available disk ${disk_gb}GB is below recommended ${MIN_DISK_GB}GB"
  fi

  if ss -ltn "( sport = :8069 )" 2>/dev/null | grep -q LISTEN; then
    warn "Port 8069 is in use. Installer will keep configured port in deploy/.env"
  fi
}

install_docker_ubuntu_debian() {
  require_sudo
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
  fi
  sudo systemctl enable --now docker
}

install_docker_rhel_family() {
  require_sudo
  if command -v dnf >/dev/null 2>&1; then
    sudo dnf -y install dnf-plugins-core
    sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
    sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
  elif command -v yum >/dev/null 2>&1; then
    sudo yum -y install yum-utils
    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo || true
    sudo yum -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
  else
    fail "Unsupported RHEL-family package manager"
  fi
  sudo systemctl enable --now docker
}

ensure_docker() {
  load_os_info
  if ! command -v docker >/dev/null 2>&1; then
    log "Docker not found, installing..."
    if [[ "$os_id" == "ubuntu" || "$os_id" == "debian" || "$os_like" == *"debian"* ]]; then
      install_docker_ubuntu_debian
    elif [[ "$os_id" == "centos" || "$os_id" == "rhel" || "$os_id" == "rocky" || "$os_id" == "almalinux" || "$os_like" == *"rhel"* || "$os_like" == *"fedora"* ]]; then
      install_docker_rhel_family
    else
      fail "Unsupported distro for auto Docker install: ${os_id:-unknown}. Install Docker manually first."
    fi
  fi

  if ! docker compose version >/dev/null 2>&1; then
    fail "docker compose plugin is missing. Please install docker-compose-plugin."
  fi

  if ! docker info >/dev/null 2>&1; then
    require_sudo
    sudo systemctl start docker || true
    if ! docker info >/dev/null 2>&1; then
      fail "Cannot access Docker daemon. Re-login user into docker group or run installer as root."
    fi
  fi
}

ensure_env_file() {
  [[ -f "$ENV_EXAMPLE" ]] || fail "Missing $ENV_EXAMPLE"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    sed -i.bak \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random_secret)|" \
      -e "s|^ODOO_ADMIN_PASSWD=.*|ODOO_ADMIN_PASSWD=$(random_secret)|" \
      "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
    log "Created deploy/.env with random passwords"
  else
    log "Using existing deploy/.env"
  fi
}

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

wait_for_health() {
  local container="$1"; local timeout="$2"; local elapsed=0
  while (( elapsed < timeout )); do
    if ! docker ps --format '{{.Names}}' | grep -qx "$container"; then
      sleep 2
      elapsed=$((elapsed + 2))
      continue
    fi
    local health
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null || true)"
    if [[ "$health" == "healthy" || "$health" == "none" ]]; then
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  return 1
}

print_summary() {
  local port admin_pass db_name
  port="$(grep -E '^ODOO_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2- || true)"
  admin_pass="$(grep -E '^ODOO_ADMIN_PASSWD=' "$ENV_FILE" | cut -d= -f2- || true)"
  db_name="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- || true)"

  echo
  echo "========================================"
  echo "Custom WMS 1.0 installation completed"
  echo "URL: http://<server-ip>:${port:-8069}/web/login"
  echo "Database: ${db_name:-odoo19_prod}"
  echo "Master Password: ${admin_pass:-please_check_env_file}"
  echo "Status command: ./installer/status.sh"
  echo "Uninstall command: ./installer/uninstall.sh"
  echo "========================================"
}

main() {
  [[ -f "$COMPOSE_FILE" ]] || fail "Missing $COMPOSE_FILE"

  log "Step 1/6 Preflight check"
  check_system_requirements

  log "Step 2/6 Ensure Docker runtime"
  ensure_docker

  log "Step 3/6 Prepare environment file"
  ensure_env_file

  log "Step 4/6 Build and start database"
  compose build odoo
  compose up -d db
  wait_for_health "$DB_CONTAINER" 180 || fail "Database container health timeout"

  log "Step 5/6 Initialize/upgrade application database"
  compose --profile init run --rm init

  log "Step 6/6 Start service and verify"
  compose up -d odoo
  wait_for_health "$APP_CONTAINER" "$WAIT_TIMEOUT_SEC" || fail "Odoo container health timeout"

  local port
  port="$(grep -E '^ODOO_HTTP_PORT=' "$ENV_FILE" | cut -d= -f2- || echo 8069)"
  curl -fsS "http://127.0.0.1:${port}/web/login" >/dev/null || fail "HTTP healthcheck failed on port ${port}"

  print_summary
}

main "$@"

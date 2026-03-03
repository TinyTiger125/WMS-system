#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-1.0.0}"
PKG_NAME="custom-wms-installer-${VERSION}"
WORK_DIR="dist/${PKG_NAME}"
ARCHIVE="dist/${PKG_NAME}.tar.gz"

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

cp -R deploy "$WORK_DIR/"
cp -R installer "$WORK_DIR/"
cp -R custom "$WORK_DIR/"
cp -R doc "$WORK_DIR/"
cp README.md "$WORK_DIR/"

find "$WORK_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$WORK_DIR" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

cat > "$WORK_DIR/INSTALL.sh" <<'BOOT'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT_DIR/installer/install.sh" "$@"
BOOT
chmod +x "$WORK_DIR/INSTALL.sh"

cat > "$WORK_DIR/VERSION" <<VER
${VERSION}
VER

tar -C dist -czf "$ARCHIVE" "$PKG_NAME"
echo "Installer bundle created: $ARCHIVE"

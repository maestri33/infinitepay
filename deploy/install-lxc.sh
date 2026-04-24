#!/usr/bin/env bash
# Install infinitepay on a Debian/Ubuntu LXC container as a systemd service.
# Run as root inside the container.
set -euo pipefail

APP_DIR=/opt/infinitepay
STATE_DIR=/var/lib/infinitepay
ETC_DIR=/etc/infinitepay
USER=infinitepay

echo "[1/6] apt deps"
apt-get update -qq
apt-get install -y --no-install-recommends python3-venv python3-pip rsync

echo "[2/6] user"
id -u "$USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$USER"

echo "[3/6] dirs"
mkdir -p "$APP_DIR" "$STATE_DIR" "$ETC_DIR"
chown -R "$USER:$USER" "$APP_DIR" "$STATE_DIR"

echo "[4/6] code sync (expect this script to live in <repo>/deploy/)"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '*.egg-info' \
  --exclude '.pytest_cache' --exclude '.git' \
  "$SRC_DIR/" "$APP_DIR/"
chown -R "$USER:$USER" "$APP_DIR"

echo "[5/6] venv + install"
sudo -u "$USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip --quiet
sudo -u "$USER" "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR" --quiet

if [ ! -f "$ETC_DIR/env" ]; then
  cat > "$ETC_DIR/env" <<EOF
IPAY_DB_PATH=$STATE_DIR/app.db
IPAY_INFINITEPAY_BASE_URL=https://api.infinitepay.io
IPAY_HTTP_TIMEOUT=15
IPAY_WORKER_POLL_SECONDS=5
# se rodar o worker dedicado, desabilite o inline no processo da API:
# IPAY_RUN_INLINE_WORKER=false
EOF
fi

echo "[6/6] systemd"
cp "$APP_DIR/deploy/infinitepay-api.service" /etc/systemd/system/
cp "$APP_DIR/deploy/infinitepay-worker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now infinitepay-api
# habilite o worker dedicado só se quiser escalar / rodar separado:
# systemctl enable --now infinitepay-worker

echo
echo "OK. Status:"
systemctl status infinitepay-api --no-pager -l | head -n 15 || true
echo
echo "Próximo passo: bater PATCH /config/ com public_api_url e validar via GET externo."

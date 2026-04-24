#!/usr/bin/env bash
# Install only the remote CLI client on another Debian/Ubuntu LXC.
set -euo pipefail

API_URL="${1:-${IPAY_API_URL:-}}"
REPO_URL="${REPO_URL:-https://github.com/maestri33/infinitepay.git}"
APP_DIR="${APP_DIR:-/opt/infinitepay-remote}"
BIN_PATH="${BIN_PATH:-/usr/local/bin/ipay-remote}"

if [ -z "$API_URL" ]; then
  echo "uso: bash deploy/install-remote-cli.sh http://10.10.10.120:8000" >&2
  echo "ou defina IPAY_API_URL=http://10.10.10.120:8000" >&2
  exit 1
fi

case "$API_URL" in
  http://*|https://*) ;;
  *)
    echo "IP da API deve incluir http:// ou https://: $API_URL" >&2
    exit 1
    ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends git python3-venv ca-certificates

if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin main
  git -C "$APP_DIR" reset --hard origin/main
else
  rm -rf "$APP_DIR"
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip --quiet
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR" --quiet

cat > "$BIN_PATH" <<EOF
#!/usr/bin/env bash
export IPAY_API_URL="${API_URL%/}"
exec "$APP_DIR/.venv/bin/ipay-remote" "\$@"
EOF
chmod +x "$BIN_PATH"

echo "OK: ipay-remote instalado em $BIN_PATH"
echo "API remota: ${API_URL%/}"
"$BIN_PATH" health

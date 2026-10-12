#!/bin/bash
# Runs ON the routing instance (sent through SSM by infra/app/deploy.sh). The app behind Caddy (Apache-2.0) with HTTPS from Let's Encrypt
# and a password on every page (basic auth; only its bcrypt hash is given here). The app listens on 127.0.0.1 only; Valhalla is reached
# on 127.0.0.1:8002/8003, so the routing ports stay closed to the public.
#   setup.sh <bucket> <host> <user> <bcrypt-hash-base64> <caddy-version>
set -euo pipefail
BUCKET="$1"; HOST="$2"; USER_="$3"; HASH="$(echo "$4" | base64 -d)"; CADDY_VER="$5"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv python3-pip libgl1 libglu1-mesa libxrender1 libxcursor1 libxft2 libxinerama1 >/dev/null   # the last six: libraries the SUMO wheel's binaries link to
mkdir -p /srv/app && cd /srv/app
aws s3 cp "s3://$BUCKET/app/traffictwin-app.tar.gz" /srv/app.tar.gz --region ap-south-1 --only-show-errors
rm -rf /srv/app/* && tar -xzf /srv/app.tar.gz -C /srv/app
[ -d /srv/venv ] || python3 -m venv /srv/venv
/srv/venv/bin/pip install -q --upgrade pip
/srv/venv/bin/pip install -q -r /srv/app/infra/app/requirements.txt
# Optional: Chronos-Bolt for the live twin (infra/app/requirements_chronos.txt; CPU torch from PyTorch's own index; the model at the
# revision RQ1 used, downloaded once into /srv/hf). If any of it fails, the app runs without it and the live twin says so.
CHRONOS=no
if [ "$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)" -gt 3000 ] && \
   /srv/venv/bin/pip install -q --index-url https://download.pytorch.org/whl/cpu torch==2.13.0 && \
   /srv/venv/bin/pip install -q -r /srv/app/infra/app/requirements_chronos.txt && \
   HF_HOME=/srv/hf /srv/venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('amazon/chronos-bolt-small', revision='772f3d25d38aec6d914c8949dab4462e2d46f5d8')" >/dev/null; then
  CHRONOS=yes
fi
echo "chronos installed: $CHRONOS"
# The Model Lab needs torch (above) and the harness's own imports
MODELLAB=no
if [ "$CHRONOS" = yes ] && /srv/venv/bin/pip install -q -r /srv/app/infra/app/requirements_modellab.txt; then MODELLAB=yes; fi
echo "model lab installed: $MODELLAB"
cat > /srv/app/.env <<ENV
TRAFFICTWIN_HOSTED=1
DHAKAFLOW_NO_OBSERVATORY=1
TRAFFICTWIN_VALHALLA_URL_DHAKA=http://127.0.0.1:8002
TRAFFICTWIN_VALHALLA_URL_LOS_ANGELES=http://127.0.0.1:8003
TRAFFICTWIN_TRAVELMUX_URL_DHAKA=http://127.0.0.1:9101
TRAFFICTWIN_TRAVELMUX_URL_LOS_ANGELES=http://127.0.0.1:9102
TRAFFICTWIN_TILES_BUCKET=$BUCKET
TRAFFICTWIN_SIGNAL_MASTS=1
HF_HOME=/srv/hf
DHAKAFLOW_BTS=/srv/app/third_party_runtime/BasicTS_legacy
DHAKAFLOW_UPSTREAM=/srv/app/third_party_runtime
SUMO_HOME=$(/srv/venv/bin/python -c 'import sumo, os; print(os.path.dirname(sumo.__file__))')
PATH=/srv/venv/bin:/usr/local/bin:/usr/bin:/bin
ENV
{ /srv/venv/bin/sumo --version || true; } | head -1 > /srv/app/SUMO_VERSION.txt    # `|| true`: sumo prints several lines; head closing the pipe early gave SIGPIPE under pipefail and stopped the script before the restart (deploy 2026-10-11 20:12)
# The map app's directions: Headway's travelmux (Apache-2.0/MIT), unchanged, pinned by digest, one per city in front of that city's
# Valhalla (reached through the Docker host gateway); listening on 127.0.0.1 only (third_party/SOURCES.md, "Map app (Headway)").
TRAVELMUX=ghcr.io/headwaymaps/travelmux@sha256:7b57fa0443d53d06ec28b4aef66e749a96de3a86a84cddcb94251cbb16f9a672
for pair in dhaka:8002:9101 los_angeles:8003:9102; do
  IFS=: read -r city vport tport <<<"$pair"
  docker rm -f "travelmux-$city" >/dev/null 2>&1 || true
  docker run -d --restart unless-stopped --name "travelmux-$city" --add-host=host.docker.internal:host-gateway \
    -p "127.0.0.1:$tport:8000" "$TRAVELMUX" "http://host.docker.internal:$vport" >/dev/null
done
cat > /etc/systemd/system/traffictwin.service <<UNIT
[Unit]
Description=TrafficTwin app (hosted, Q5)
After=network.target docker.service
[Service]
WorkingDirectory=/srv/app
EnvironmentFile=/srv/app/.env
Environment=PYTHONPATH=/srv/app:/srv/app/backend
ExecStart=/srv/venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
if ! command -v caddy >/dev/null; then
  curl -fsSL -o /tmp/caddy.tgz "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VER}/caddy_${CADDY_VER}_linux_amd64.tar.gz"
  tar -xzf /tmp/caddy.tgz -C /usr/local/bin caddy && chmod +x /usr/local/bin/caddy
fi
mkdir -p /etc/caddy /var/lib/caddy
cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
	basic_auth {
		$USER_ $HASH
	}
	encode zstd gzip
	reverse_proxy 127.0.0.1:8000
	header {
		Strict-Transport-Security "max-age=31536000"
		Permissions-Policy "geolocation=(self), accelerometer=(self), gyroscope=(self)"
		-Server
	}
}
CADDY
cat > /etc/systemd/system/caddy.service <<UNIT
[Unit]
Description=Caddy (HTTPS and the password for the hosted app)
After=network-online.target
[Service]
Environment=XDG_DATA_HOME=/var/lib/caddy XDG_CONFIG_HOME=/var/lib/caddy
ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
Restart=always
AmbientCapabilities=CAP_NET_BIND_SERVICE
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now traffictwin caddy
systemctl restart traffictwin caddy
sleep 8
curl -s -o /dev/null -w "app on 127.0.0.1:8000 -> %{http_code}\n" http://127.0.0.1:8000/
systemctl is-active traffictwin caddy
cat /srv/app/SUMO_VERSION.txt

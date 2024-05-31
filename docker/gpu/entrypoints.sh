#!/bin/bash

set -e

if [ ! -d "/app/ComfyUI/custom_nodes/ComfyUI-Manager" ]; then
    mkdir -p /app/ComfyUI/custom_nodes
    cp -r /tmp/custom_nodes/ComfyUI-Manager /app/ComfyUI/custom_nodes/
fi

if [ ! -d "/app/ComfyUI/custom_nodes/Comfyfile" ]; then
    mkdir -p /app/ComfyUI/custom_nodes
    cp -r /tmp/custom_nodes/Comfyfile /app/ComfyUI/custom_nodes/
fi

if [ ! -d "/app/ComfyUI/custom_nodes/ComfyUI-KJNodes" ]; then
    mkdir -p /app/ComfyUI/custom_nodes
    cp -r /tmp/custom_nodes/ComfyUI-KJNodes /app/ComfyUI/custom_nodes/
fi

if [ -n "$CLASH_SUBSCRIPTION_URL" ]; then

echo "CLASH_SUBSCRIPTION_URL is configured, auto setup clash..."

cat <<EOL > /app/clash-for-linux/.env
export CLASH_URL='$CLASH_SUBSCRIPTION_URL'
export CLASH_SECRET='$CLASH_SECRET'
EOL

bash /app/clash-for-linux/start.sh
source /etc/profile.d/clash.sh
proxy_on

wait_for_proxy() {
  local host="127.0.0.1"
  local port="7890"

  echo "Waiting for $host:$port to be accessible..."

  while ! (echo > /dev/tcp/$host/$port) &> /dev/null; do
    sleep 1
  done

  echo "$host:$port is now accessible!"
}

wait_for_proxy

else
    echo "Clash is not enabled"
fi

# Copy /venv to /app/ComfyUI/venv
if [ ! -d "/app/ComfyUI/venv/bin" ]; then

echo "Copying python libraries from /venv to /app/ComfyUI/venv ..."

python3 /app/clonevirtualenv.py /venv /app/ComfyUI/venv

fi

# Change to the /app/ComfyUI directory
cd /app/ComfyUI

source /app/ComfyUI/venv/bin/activate


upgrade_comfyfile() {
    local max_retries=3
    local attempt=1

    while (( attempt <= max_retries )); do
        if [ -n "$AUTO_UPGRADE_COMFYFILE" ]; then
            echo "Attempt $attempt: Auto upgrading https://github.com/inf-monkeys/Comfyfile"
            rm -rf /app/ComfyUI/custom_nodes/Comfyfile

            if git clone --depth=1 --no-tags --recurse-submodules --shallow-submodules https://github.com/inf-monkeys/Comfyfile /app/ComfyUI/custom_nodes/Comfyfile; then
                if pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/Comfyfile/requirements.txt; then
                    echo "Upgrade successful"
                    return 0
                else
                    echo "pip install failed on attempt $attempt. Retrying..."
                fi
            else
                echo "git clone failed on attempt $attempt. Retrying..."
            fi
        else
            echo "AUTO_UPGRADE_COMFYFILE is disabled"
            return 1
        fi

        ((attempt++))
    done

    echo "Upgrade failed after $max_retries attempts"
    return 1
}


upgrade_comfyfile


exec python3 main.py --listen 0.0.0.0

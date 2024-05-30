#!/bin/bash

set -e

if [ ! -d "/app/ComfyUI/custom_nodes/ComfyUI-Manager" ]; then
    mkdir -p /app/ComfyUI/custom_nodes
    cp -r /tmp/custom_nodes/ComfyUI-Manager /app/ComfyUI/custom_nodes/
    cp -r /tmp/custom_nodes/Comfyfile /app/ComfyUI/custom_nodes/
fi

if [ ! -d "/app/ComfyUI/venv/bin" ]; then
    mkdir -p /app/ComfyUI/venv/
    cp -r /tmp/venv /app/ComfyUI/
fi

# Change to the /app/ComfyUI directory
cd /app/ComfyUI

source venv/bin/activate

TCP_READ_TIMEOUT=${PROXY_TCP_READ_TIMEOUT:-15000}
TCP_CONNECT_TIMEOUT=${PROXY_TCP_CONNECT_TIMEOUT:-8000}

cat <<EOL > /etc/proxychains.conf
strict_chain

# Some timeouts in milliseconds
tcp_read_time_out $TCP_READ_TIMEOUT
tcp_connect_time_out $TCP_CONNECT_TIMEOUT

[ProxyList]
http $PROXY_HOST $PROXY_PORT
EOL

if [ -n "$AUTO_UPGRADE_COMFYFILE" ]; then
    echo "Auto upgrading https://github.com/inf-monkeys/Comfyfile"
    rm -rf /app/ComfyUI/custom_nodes/Comfyfile
    git clone --depth=1 --no-tags --recurse-submodules --shallow-submodules https://github.com/inf-monkeys/Comfyfile /app/ComfyUI/custom_nodes/Comfyfile
    pip install --no-cache-dir -r /app/ComfyUI/custom_nodes/Comfyfile/requirements.txt
else
    echo "AUTO_UPGRADE_COMFYFILE is disabled"
fi

if [ -z "$PROXY_HOST" ] || [ -z "$PROXY_PORT" ]; then
    echo "Proxy not configured"
    # Run the python script directly if no proxy is set
    exec python3 main.py --listen 0.0.0.0
else
    echo "Use proxy http://$PROXY_HOST:$PROXY_PORT"
    exec proxychains python3 main.py --listen 0.0.0.0
fi

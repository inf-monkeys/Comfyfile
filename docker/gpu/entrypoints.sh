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

# Proxychains configuration file
proxychains_config_file="/etc/proxychains.conf"

# Check if the PROXYCHAINS_PROXY_SERVER environment variable is set
if [ -z "$PROXYCHAINS_PROXY_SERVER" ]; then
    echo "NO PROXYCHAINS_PROXY_SERVER ENVIRONMENT VARIABLE FOUND, WILL NOT USE PROXYCHAINS."
else
    # If the PROXYCHAINS_PROXY_SERVER environment variable is set, check if it is in the proxychains configuration file
    if ! grep -Fxq "$PROXYCHAINS_PROXY_SERVER" "$proxychains_config_file"; then
        # Add the proxy server to the end of the proxychains configuration file
        echo "$PROXYCHAINS_PROXY_SERVER" | sudo tee -a "$proxychains_config_file" > /dev/null
        echo "Added $PROXYCHAINS_PROXY_SERVER to $proxychains_config_file."
    fi
fi

# If a proxy is found, set the necessary environment variables and use proxychains
if [ -n "$PROXYCHAINS_PROXY" ] && [ -n "$PROXY_PORT" ]; then
    exec proxychains python3 main.py --listen 0.0.0.0
else
    # Run the python script directly if no proxy is set
    exec python3 main.py --listen 0.0.0.0
fi

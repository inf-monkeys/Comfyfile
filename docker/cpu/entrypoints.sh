#!/bin/bash

set -e

# Function to extract host and port from a proxy URL
extract_host_port() {
    local url=$1
    local proto="$(echo $url | grep '://' | sed -e's,^\(.*://\).*,\1,g')"
    local hostport="$(echo ${url/$proto/} | cut -d/ -f1)"
    local host="$(echo $hostport | cut -d: -f1)"
    local port="$(echo $hostport | cut -d: -f2)"
    echo $host $port
}

# Check for http_proxy or https_proxy environment variables
if [ -n "$http_proxy" ]; then
    read PROXY_HOST PROXY_PORT <<< $(extract_host_port $http_proxy)
elif [ -n "$https_proxy" ]; then
    read PROXY_HOST PROXY_PORT <<< $(extract_host_port $https_proxy)
fi

if [ ! -d "/app/ComfyUI/custom_nodes/" ]; then
    mkdir -p /app/ComfyUI/custom_nodes/
    cp -r /tmp/ComfyUI-Manager/* /app/ComfyUI/custom_nodes/
fi

# Change to the /app/ComfyUI directory
cd /app/ComfyUI

# If a proxy is found, set the necessary environment variables and use proxychains
if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
    export PROXYCHAINS_SOCKS5_HOST=$PROXY_HOST
    export PROXYCHAINS_SOCKS5_PORT=$PROXY_PORT
    exec proxychains python main.py --cpu --listen 0.0.0.0
else
    # Run the python script directly if no proxy is set
    exec python main.py --cpu --listen 0.0.0.0
fi

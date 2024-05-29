FROM python:3.10-slim

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

RUN apt-get update && \
    apt-get install vim wget curl build-essential git proxychains git-lfs  -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ComfyUI
# Note that we clone ComfyUI-Manager to /tmp and mv it from /tmp to /app/ComfyUI/custom_nodes in entrypoint-cpu.sh
RUN git clone https://github.com/comfyanonymous/ComfyUI && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager /tmp/ComfyUI-Manager && \
    git clone https://github.com/inf-monkeys/Comfyfile /tmp/Comfyfile && \
    pip install --no-cache-dir -r ./ComfyUI/requirements.txt && \
    pip install --no-cache-dir -r /tmp/ComfyUI-Manager/requirements.txt && \
    pip install --no-cache-dir -r /tmp/Comfyfile/requirements.txt

EXPOSE 8188

COPY ./docker/comfyui/entrypoint-cpu.sh ./entrypoint-cpu.sh

# Run the app
CMD ["./entrypoint-cpu.sh"]

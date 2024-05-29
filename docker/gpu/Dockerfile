FROM nvidia/cuda:12.0.0-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
RUN apt-get update && \
    apt-get install git default-jre python3 python3-pip python3.10-venv vim wget curl git git-lfs proxychains -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /tmp/venv

# Install Python dependencies
RUN /tmp/venv/bin/pip install --upgrade pip && \
    /tmp/venv/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install ComfyUI
# Note that we clone ComfyUI-Manager to /tmp and mv it from /tmp to /app/ComfyUI/custom_nodes in entrypoint-gpu.sh
RUN git clone https://github.com/comfyanonymous/ComfyUI && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager /tmp/ComfyUI-Manager && \
    pip install --no-cache-dir -r ./ComfyUI/requirements.txt && \
    pip install --no-cache-dir -r /tmp/ComfyUI-Manager/requirements.txt

COPY . /app/ComfyUI/custom_nodes/Comfyfile

RUN /tmp/venv/bin/pip install -r /app/ComfyUI/custom_nodes/Comfyfile/requirements.txt

EXPOSE 8188

COPY ./docker/gpu/entrypoints.sh ./entrypoints.sh

# Run the app
CMD ["./entrypoints.sh"]

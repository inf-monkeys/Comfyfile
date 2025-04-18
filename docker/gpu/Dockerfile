FROM nvidia/cuda:12.0.0-cudnn8-runtime-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
RUN apt-get update && \
    apt-get install git default-jre python3 python3-pip python3.10-venv vim wget lsof curl git git-lfs proxychains aria2 -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /venv

# Install Python dependencies
RUN /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install ComfyUI
# Note that we clone ComfyUI-Manager to /tmp and mv it from /tmp to /app/ComfyUI/custom_nodes in entrypoint-gpu.sh
RUN git clone --depth=1 --no-tags --recurse-submodules --shallow-submodules https://github.com/comfyanonymous/ComfyUI && \
    git clone --depth=1 --no-tags --recurse-submodules --shallow-submodules https://github.com/ltdrdata/ComfyUI-Manager /tmp/custom_nodes/ComfyUI-Manager && \
    git clone --depth=1 --no-tags --recurse-submodules --shallow-submodules https://github.com/kijai/ComfyUI-KJNodes /tmp/custom_nodes/ComfyUI-KJNodes && \
    /venv/bin/pip install --no-cache-dir -r ./ComfyUI/requirements.txt && \
    /venv/bin/pip install --no-cache-dir -r /tmp/custom_nodes/ComfyUI-Manager/requirements.txt && \
    /venv/bin/pip install --no-cache-dir -r /tmp/custom_nodes/ComfyUI-KJNodes/requirements.txt

# 确保 comfyui-frontend-package 已安装
RUN /venv/bin/pip install --no-cache-dir comfyui-frontend-package

# Install Clash
RUN git clone https://github.com/wnlen/clash-for-linux/

RUN wget https://hf-mirror.com/hfd/hfd.sh && chmod a+x hfd.sh && mv hfd.sh /usr/bin/hfd

COPY ./requirements.txt /tmp/custom_nodes/Comfyfile/requirements.txt

RUN /venv/bin/pip install -r /tmp/custom_nodes/Comfyfile/requirements.txt

COPY . /tmp/custom_nodes/Comfyfile

EXPOSE 8188

COPY ./docker/gpu/entrypoints.sh /app/entrypoints.sh
COPY ./docker/gpu/clonevirtualenv.py /app/clonevirtualenv.py

# Run the app
CMD ["./entrypoints.sh"]

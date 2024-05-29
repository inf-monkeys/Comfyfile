## Quick Start

### 🐳 Docker

1. Build Docker Image

    For GPU Environment:

    ```sh
    docker build . -t infmonkeys/comfyui:latest-gpu -f docker/gpu/Dockerfile
    ```

2. Run Docker Container

    For GPU Environment:

    ```sh
    docker run --gpus all -v ./ComfyUI/models:/app/ComfyUI/models -v ./ComfyUI/input:/app/ComfyUI/input -v ./ComfyUI/output:/app/ComfyUI/output -v ./ComfyUI/custom_nodes:/app/ComfyUI/custom_nodes -p 8188:8188  --name comfyui -d infmonkeys/comfyui:latest-gpu
    ```

    or 

    ```sh
    docker run --gpus all -p 8188:8188  --name comfyui -d infmonkeys/comfyui:latest-gpu
    ```

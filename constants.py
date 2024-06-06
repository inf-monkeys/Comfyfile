import os
from comfy.cli_args import args
import folder_paths

APP_HOST = 'http://127.0.0.1'
APP_PORT = args.port

MODEL_DOWNLOAD_PATH_LIST = [
    "./custom_nodes/Comfyfile/models/civit_model_weights.json",
    "./custom_nodes/Comfyfile/models/replicate_model_weights.json",
    "./custom_nodes/Comfyfile/models/huggingface_weights.json",
]
COMFY_MODEL_PATH_LIST = [
    "./custom_nodes/ComfyUI-Manager/model-list.json",
    "./custom_nodes/Comfyfile/models/extra_comfy_weights.json",
]

# enable this to view comfy console logs and other debug statements
DEBUG_LOG_ENABLED = True

# these models are downloaded automatically during the runtime (install manually if not present)
OPTIONAL_MODELS = ["stmfnet.pth"]

MODEL_FILETYPES = [
    ".ckpt",
    ".safetensors",
    ".pt",
    ".pth",
    ".bin",
    ".onnx",
    ".torchscript",
    ".patch",
    ".gguf",
    ".ggml",
]

# paths
comfyfile_path = os.path.dirname(__file__)
comfy_path = os.path.dirname(folder_paths.__file__)
custom_nodes_path = os.path.join(comfy_path, "custom_nodes")
js_path = os.path.join(comfy_path, "web", "extensions")
models_path = os.path.join(comfy_path, "models")
input_path = os.path.join(comfy_path, "input")
output_path = os.path.join(comfy_path, "output")
config_folder = os.path.join(comfyfile_path, "config")
if not os.path.exists(config_folder):
    os.mkdir(config_folder)
s3_config_file = os.path.join(config_folder, "s3.json")
workflows_folder = os.path.join(comfyfile_path, "workflows")
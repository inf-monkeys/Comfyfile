import asyncio
import hashlib
import os.path
import shutil
import traceback
import zipfile
import server
import sys
import json
import uuid
import logging
import boto3
from botocore.client import Config
from .comfyfile_downloader import download_github_directory
from .buildkit import ComfyfileExecutor, ComfyfileParser
from .runner import ComfyRunner
from loguru import logger
from .constants import (
    comfy_path,
    comfyfile_path,
    js_path,
    s3_config_file,
    workflows_folder,
    local_workflows_folder,
)
import os
import subprocess

S3_ENABLED = os.environ.get("S3_ENABLED")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY")
S3_REGION = os.environ.get("S3_REGION")
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_PUBLIC_ACCESS_URL = os.environ.get("S3_PUBLIC_ACCESS_URL")
S3_ADDRESSING_STYLE = os.environ.get("S3_ADDRESSING_STYLE", "auto")

if (
    S3_ENABLED
    and S3_ENDPOINT_URL
    and S3_ACCESS_KEY_ID
    and S3_SECRET_ACCESS_KEY
    and S3_REGION
    and S3_BUCKET
    and S3_PUBLIC_ACCESS_URL
    and S3_ADDRESSING_STYLE
):
    with open(s3_config_file, "w") as f:
        f.write(
            json.dumps(
                {
                    "enabled": True,
                    "endpoint_url": S3_ENDPOINT_URL,
                    "aws_access_key_id": S3_ACCESS_KEY_ID,
                    "aws_secret_access_key": S3_SECRET_ACCESS_KEY,
                    "region_name": S3_REGION,
                    "addressing_style": S3_ADDRESSING_STYLE,
                    "bucket": S3_BUCKET,
                    "public_access_url": S3_PUBLIC_ACCESS_URL,
                }
            )
        )


logging.basicConfig(
    format="[%(name)s] %(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
# 创建日志记录器
logger = logging.getLogger("Comfyfile")

home_directory = os.path.expanduser("~")
comfyfile_home_dir = os.path.join(home_directory, ".cache/Comfyfile")

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    print("Module 'aiohttp' not installed. Please install it via:")
    print("pip install aiohttp")
    print("or")
    print("pip install -r requirements.txt")
    sys.exit()


async def import_from_remote_comfyfile_repo(comfyfile_repo):
    random_id = uuid.uuid4().hex
    comfyfile_tmp_folder = os.path.join(comfyfile_home_dir, random_id)
    download_github_directory(comfyfile_repo, comfyfile_tmp_folder)
    comfyfile_path = os.path.join(comfyfile_tmp_folder, "Comfyfile")
    if not os.path.exists(comfyfile_path):
        raise Exception("Invalid comfyfile repo, Comfyfile not found")
    context_directory = comfyfile_tmp_folder
    comfyfile_app = ComfyfileParser(comfyfile_path, context_directory).parse_comfyfile()
    executor = ComfyfileExecutor(context_directory, comfy_path)
    await executor.process_comfyfile_apps(comfyfile_app)


async def import_from_local_comfyfile_repo(local_comfyfile_repo):
    local_comfyfile = os.path.join(local_comfyfile_repo, "Comfyfile")
    comfyfile_apps = ComfyfileParser(local_comfyfile, local_comfyfile_repo).parse_comfyfile()
    if len(comfyfile_apps) == 0:
        raise Exception("No apps found in Comfyfile, please check the Comfyfile format.")
    executor = ComfyfileExecutor(local_comfyfile_repo, comfy_path)
    await executor.process_comfyfile_apps(comfyfile_apps)
    dot_installed_file = os.path.join(local_comfyfile_repo, ".installed")
    with open(dot_installed_file, "w") as f:
        f.write("")
    return comfyfile_apps


@server.PromptServer.instance.routes.post("/comfyfile/apps")
async def import_app(request):
    json_data = await request.json()
    comfyfile_repo = json_data.get("comfyfile_repo")
    local_comfyfile_repo = json_data.get("local_comfyfile_repo")
    if not comfyfile_repo and not local_comfyfile_repo:
        return web.json_response(
            {"success": False, "errMsg": "Comfyfile repo is required"}
        )
    try:
        if comfyfile_repo:
            await import_from_remote_comfyfile_repo(comfyfile_repo)
        elif local_comfyfile_repo:
            await import_from_local_comfyfile_repo(os.path.join(workflows_folder, local_comfyfile_repo))
        return web.json_response({"success": True, "errMsg": "Install success"})
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"success": False, "errMsg": str(e)})


@server.PromptServer.instance.routes.post("/comfyfile/apps/reinstall")
async def import_app(request):
    json_data = await request.json()
    comfyfile_repo = json_data.get("comfyfile_repo")
    local_comfyfile_repo = json_data.get("local_comfyfile_repo")
    if not comfyfile_repo and not local_comfyfile_repo:
        return web.json_response(
            {"success": False, "errMsg": "Comfyfile repo is required"}
        )
    try:
        if comfyfile_repo:
            await import_from_remote_comfyfile_repo(comfyfile_repo)
        elif local_comfyfile_repo:
            dot_installed_file = os.path.join(local_comfyfile_repo, ".installed")
            if os.path.exists(dot_installed_file):
                os.remove(dot_installed_file)
            await import_from_local_comfyfile_repo(os.path.join(workflows_folder, local_comfyfile_repo))
        return web.json_response({"success": True, "errMsg": "Install success"})
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"success": False, "errMsg": str(e)})

def extract_comfyfile_zip(zip_path, extract_path):
    # 检查 zip 文件是否存在
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Zip file '{zip_path}' not found.")
    
    # 创建解压目录（如果不存在）
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)
    
    # 解压文件
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
        
    os.remove(zip_path)

    # 检查解压后的内容是否为一个目录
    extracted_items = os.listdir(extract_path)
    if len(extracted_items) != 1 or not os.path.isdir(os.path.join(extract_path, extracted_items[0])):
        raise ValueError("The extracted content is not a single directory.")
    
    # 返回解压后的目录路径
    return os.path.join(extract_path, extracted_items[0])


@server.PromptServer.instance.routes.post("/comfyfile/apps/zip")
async def import_app(request):
    try:
        reader = await request.multipart()
        field = await reader.next()
        assert field.name == 'file'
        filename = field.filename
        size = 0
        random_id = str(uuid.uuid4())
        zip_file = os.path.join(local_workflows_folder, random_id, filename)
        if not os.path.exists(os.path.dirname(zip_file)):
            os.makedirs(os.path.dirname(zip_file))
        with open(zip_file, 'wb') as f:
            while True:
                chunk = await field.read_chunk()  # 8192 bytes by default.
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)
        extracted_folder = extract_comfyfile_zip(zip_file, os.path.join(local_workflows_folder, random_id))
        logger.info(f"Extracted comfyfile zip to folder: {extracted_folder}")
        apps = await import_from_local_comfyfile_repo(extracted_folder)
        return web.json_response({"success": True, "errMsg": "Install success", "apps": [app.serialize() for app in apps]})
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"success": False, "errMsg": str(e)})

@server.PromptServer.instance.routes.get("/comfyfile/apps")
async def list_apps(request):
    if not os.path.exists(workflows_folder):
        return web.json_response({"list": []})
    subfolders = [f.path for f in os.scandir(workflows_folder) if f.is_dir()]
    all_apps = []
    for subfolder in subfolders:
        comfyfile_path = os.path.join(subfolder, "Comfyfile")
        comfyfile_parser = ComfyfileParser(
            comfyfile_path=comfyfile_path,
            context_directory=subfolder,
        )
        apps = comfyfile_parser.parse_comfyfile()
        for app in apps:
            app_info = app.serialize()
            dot_installed_file = os.path.join(subfolder, ".installed")
            installed = os.path.exists(dot_installed_file)
            app_info.update(
                {"folder": os.path.basename(subfolder), "installed": installed}
            )
            all_apps.append(app_info)
    return web.json_response({"list": all_apps})


@server.PromptServer.instance.routes.post("/comfyfile/run")
async def run_comfyui_workflow(request):
    body = await request.json()
    workflow_json = body.get("workflow_json")
    workflow_api_json = body.get("workflow_api_json")
    input_data = body.get("input_data")
    app_name = body.get("app_name")

    input_config = body.get("input_config")
    output_config = body.get("output_config")
    if not app_name:
        if not workflow_json:
            raise Exception("workflow_json is empty")
        if not workflow_api_json:
            raise Exception("workflow_api_json is empty")
    else:
        app_folder = os.path.join(workflows_folder, app_name)
        comfyfile_path = os.path.join(app_folder, "Comfyfile")
        dot_installed_file = os.path.join(app_folder, ".installed")
        if not os.path.exists(dot_installed_file):
            raise Exception(f"App {app_name} is not installed")
        comfyfile_parser = ComfyfileParser(
            comfyfile_path=comfyfile_path,
            context_directory=app_folder,
        )
        app = comfyfile_parser.parse_comfyfile()[0]
        workflow_json = app.workflow
        workflow_api_json = app.workflowApi
        input_config = app.restEndpoint["parameters"]
        output_config = app.restEndpoint.get('output')

    # comfyfile_repo = body.get("comfyfile_repo")
    # if comfyfile_repo:
    #     await import_from_remote_comfyfile_repo(comfyfile_repo)
    runner = ComfyRunner()
    logger.info(
        f"Received a request: workflow_json={workflow_json}, workflow_api_json={workflow_api_json} input_data={input_data} input_config={input_config} output_config={output_config}"
    )
    output = await runner.predict(
        workflow_json=workflow_json,
        workflow_api_json=workflow_api_json,
        input_data=input_data,
        input_config=input_config,
        output_config=output_config
    )
    return web.json_response(output)


@server.PromptServer.instance.routes.post("/comfyfile/check-dependencies")
async def check_dependencies(request):
    body = await request.json()
    workflow_json = body.get("workflow_json")
    workflow_api_json = body.get("workflow_api_json")
    runner = ComfyRunner()
    data = await runner.infer_dependencies(workflow_json, workflow_api_json)
    return web.json_response(data)


@server.PromptServer.instance.routes.get("/comfyfile/healthz")
async def get_manifest_json(request):
    return web.json_response({"success": True})

@server.PromptServer.instance.routes.get('/comfyfile/model-list')
async def get_model_list(request):
    result = []
    for root, _, files in os.walk('./models'):
        for file in files:
            if file.endswith(tuple(['.ckpt', '.pt', '.pth', '.bin', '.safetensors'])):
                relative_path = os.path.relpath(os.path.join(root, file), './models')
                hash_md5 = hashlib.md5()
                with open(os.path.join(root, file), "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                result.append({
                    "path": relative_path,
                    "md5": hash_md5.hexdigest()
                })
    return web.json_response(result)


async def test_s3_connection(json_data):
    endpoint_url = json_data.get("endpoint_url")
    aws_access_key_id = json_data.get("aws_access_key_id")
    aws_secret_access_key = json_data.get("aws_secret_access_key")
    region_name = json_data.get("region_name")
    addressing_style = json_data.get("addressing_style", "auto")
    bucket = json_data.get("bucket")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
        config=Config(s3={"addressing_style": addressing_style}),
    )
    s3.head_bucket(Bucket=bucket)


@server.PromptServer.instance.routes.post("/comfyfile/test-s3")
async def test_s3(request):
    json_data = await request.json()
    try:
        await asyncio.wait_for(test_s3_connection(json_data), timeout=3)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "errMsg": str(e)})


@server.PromptServer.instance.routes.post("/comfyfile/save-s3-config")
async def save_s3_config(request):
    json_data = await request.json()
    enabled = json_data.get("enabled")
    endpoint_url = json_data.get("endpoint_url")
    aws_access_key_id = json_data.get("aws_access_key_id")
    aws_secret_access_key = json_data.get("aws_secret_access_key")
    region_name = json_data.get("region_name")
    addressing_style = json_data.get("addressing_style", "auto")
    public_access_url = json_data.get("public_access_url")
    bucket = json_data.get("bucket")
    with open(s3_config_file, "w") as f:
        f.write(
            json.dumps(
                {
                    "enabled": enabled,
                    "endpoint_url": endpoint_url,
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                    "region_name": region_name,
                    "addressing_style": addressing_style,
                    "bucket": bucket,
                    "public_access_url": public_access_url,
                }
            )
        )
    return web.json_response({"success": True})


@server.PromptServer.instance.routes.get("/comfyfile/get-s3-config")
async def get_s3_config(request):
    if os.path.exists(s3_config_file):
        try:
            with open(s3_config_file, "r", encoding="utf-8") as f:
                return web.json_response({"success": True, "data": json.load(f)})
        except Exception as e:
            return web.json_response({"success": False, "errMsg": str(e)})
    else:
        return web.json_response({"success": False})


def setup_js():
    import nodes

    js_dest_path = os.path.join(js_path, "comfyfile")

    if hasattr(nodes, "EXTENSION_WEB_DIRS"):
        if os.path.exists(js_dest_path):
            shutil.rmtree(js_dest_path)
    else:
        logger.warning(
            f"Your ComfyUI version is outdated. Please update to the latest version."
        )
        # setup js
        if not os.path.exists(js_dest_path):
            os.makedirs(js_dest_path)
        js_src_path = os.path.join(comfyfile_path, "js", "comfyfile.js")

        print(f"### Comfyfile: Copy .js from '{js_src_path}' to '{js_dest_path}'")
        shutil.copy(js_src_path, js_dest_path)


def setup_webapp():
    subprocess.Popen(
        [
            "streamlit",
            "run",
            "custom_nodes/Comfyfile/webapp.py",
            "--server.headless",
            "true",
        ],
        cwd=comfy_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


WEB_DIRECTORY = "js"
setup_js()
setup_webapp()

NODE_CLASS_MAPPINGS = {}

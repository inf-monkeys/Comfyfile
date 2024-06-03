import asyncio
from copy import deepcopy
import os.path
import shutil
import traceback
import requests
import server
import sys
import json
import uuid
import logging
import boto3
from botocore.client import Config
from .comfyfile_downloader import download_github_directory
from .buildkit import Executor, Comfyfile
from .runner import ComfyRunner
from loguru import logger
from .constants import comfy_path, comfyfile_path, js_path, s3_config_file
import os

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


def ensure_directory_exists(dir_path):
    """
    如果目录不存在则创建目录
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


def download_file_to(file_url, to):
    logger.info(f"Downloading file from {file_url} to {to}")
    response = requests.get(file_url, stream=True)
    response.raise_for_status()
    ensure_directory_exists(os.path.dirname(to))
    with open(to, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return to


def download_and_replace_remote_files(input_data):
    input_data = deepcopy(input_data)
    file_paths = []
    for node_id in input_data:
        node_input = input_data[node_id]
        for key in node_input:
            value = node_input[key]
            if isinstance(value, str) and (
                value.startswith("http://") or value.startswith("https://")
            ):
                file_extension = value.split("?")[0].split(".")[-1]
                if file_extension:
                    file_filename = str(uuid.uuid4()) + "." + file_extension
                    file_path = os.path.join("./input/", file_filename)
                    download_file_to(value, file_path)
                    file_paths.append(file_path)
                    node_input[key] = file_filename
    return input_data, file_paths


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


async def import_from_comfyfile_repo(comfyfile_repo):
    random_id = uuid.uuid4().hex
    comfyfile_tmp_folder = os.path.join(comfyfile_home_dir, random_id)
    download_github_directory(comfyfile_repo, comfyfile_tmp_folder)
    comfyfile_path = os.path.join(comfyfile_tmp_folder, "Comfyfile")
    if not os.path.exists(comfyfile_path):
        raise Exception("Invalid comfyfile repo, Comfyfile not found")
    context_directory = comfyfile_tmp_folder
    comfyfile = Comfyfile().parse_comfyfile(comfyfile_path)
    executor = Executor(context_directory, comfy_path)
    await executor.process_comfyfile(comfyfile)


@server.PromptServer.instance.routes.post("/comfyfile/apps")
async def import_app(request):
    json_data = await request.json()
    comfyfile_repo = json_data.get("comfyfile_repo")
    if not comfyfile_repo:
        return web.json_response(
            {"success": False, "errMsg": "Comfyfile repo is required"}
        )
    try:
        await import_from_comfyfile_repo(comfyfile_repo)
        return web.json_response({"success": True, "errMsg": "Install success"})
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"success": False, "errMsg": str(e)})


@server.PromptServer.instance.routes.get("/comfyfile/apps")
async def list_apps(request):
    apps_folder = os.path.join(os.path.dirname(__file__), "apps")
    if not os.path.exists(apps_folder):
        return web.json_response({"list": []})
    subfolders = [f.path for f in os.scandir(apps_folder) if f.is_dir()]

    apps = []
    for subfolder in subfolders:
        app = {"appName": os.path.basename(os.path.normpath(subfolder))}
        manifest_json_file = os.path.join(subfolder, "manifest.json")
        if os.path.exists(manifest_json_file):
            with open(manifest_json_file, "r", encoding="utf-8") as f:
                app.update(json.loads(f.read()))
        workflow_json_file = os.path.join(subfolder, "workflow.json")
        with open(workflow_json_file, "r", encoding="utf-8") as f:
            app.update({"workflow": json.loads(f.read())})
        apps.append(app)
    return web.json_response({"list": apps})


@server.PromptServer.instance.routes.post("/comfyfile/run")
async def run_comfyui_workflow(request):
    body = await request.json()
    workflow_json = body.get("workflow_json")
    workflow_api_json = body.get("workflow_api_json")
    input_data = body.get("input_data")
    if not workflow_json:
        raise Exception("workflow_json is empty")
    if not workflow_api_json:
        raise Exception("workflow_api_json is empty")
    comfyfile_repo = body.get("comfyfile_repo")
    if comfyfile_repo:
        await import_from_comfyfile_repo(comfyfile_repo)
    if input_data:
        input_data, file_path_list = download_and_replace_remote_files(input_data)
    file_path_list = []
    runner = ComfyRunner()
    logger.info(
        f"Received a request: workflow_json={workflow_json}, workflow_api_json={workflow_api_json} input_data={input_data}"
    )
    output = await runner.predict(
        workflow_json=workflow_json,
        workflow_api_json=workflow_api_json,
        input_data=input_data,
        file_path_list=file_path_list,
    )
    return web.json_response(output)


@server.PromptServer.instance.routes.post("/comfyfile/check-dependencies")
async def check_dependencies(request):
    body = await request.json()
    comfyfile_repo = body.get("comfyfile_repo")
    workflow = body.get("workflow")
    runner = ComfyRunner()
    data = await runner.infer_dependencies(workflow)
    return web.json_response(data)


@server.PromptServer.instance.routes.get("/comfyfile/healthz")
async def get_manifest_json(request):
    return web.json_response({"success": True})


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


WEB_DIRECTORY = "js"
setup_js()

NODE_CLASS_MAPPINGS = {}

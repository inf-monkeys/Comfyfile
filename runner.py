import json
import os
import random
import subprocess
import re
import websockets
import uuid
from loguru import logger
from .constants import (
    MODEL_DOWNLOAD_PATH_LIST,
    MODEL_FILETYPES,
    OPTIONAL_MODELS,
    APP_HOST,
    APP_PORT,
    s3_config_file,
    output_path,
)
from .api import BaseAPI, ComfyAPI
from .common import (
    download_file_to,
    search_model,
)
from .model_downloader import FileStatus, ModelDownloader
from loguru import logger
import boto3
from botocore.client import Config


def is_command_installed(command):
    try:
        # Run 'which' command to check if the command exists
        result = subprocess.run(
            ["which", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # If the return code is 0, the command is found
        return result.returncode == 0
    except Exception as e:
        # Handle any exception that may occur
        print(f"An error occurred: {e}")
        return False


class ComfyRunner:
    def __init__(self):
        self.comfy_api = ComfyAPI(APP_HOST, APP_PORT)
        self.model_downloader = ModelDownloader(MODEL_DOWNLOAD_PATH_LIST)

    async def run_prompt(self, prompt, output_config=None):
        client_id = str(uuid.uuid4())
        logger.info(
            f"Start to run comfyui workflow: client_id={client_id}, workflow={prompt}"
        )
        prompt_result = await self.comfy_api.queue_prompt(prompt, client_id)
        logger.info(f"Queue comfyui workflow result: {prompt_result}")
        if not prompt_result.get("prompt_id"):
            error_msg = prompt_result.get("error")
            node_errors = prompt_result.get("node_errors")
            raise Exception(
                f"Failed to start comfyui workflow: {error_msg}, {node_errors}"
            )
        prompt_id = prompt_result["prompt_id"]

        host = APP_HOST + ":" + str(APP_PORT)
        host = host.replace("http://", "").replace("https://", "")
        ws_url = "ws://{}/ws?clientId={}".format(host, client_id)
        logger.info(f"Connecting ws to: {ws_url}")
        async with websockets.connect(ws_url) as websocket:
            logger.info("Ws connected")
            while True:
                try:
                    out = await websocket.recv()
                    if isinstance(out, str):
                        message = json.loads(out)
                        logger.info(f"Ws received: {out[0:100]}...")
                        if message["type"] == "executing":
                            data = message["data"]
                            if data["node"] is None and data["prompt_id"] == prompt_id:
                                break  # Execution is done
                        elif message["type"] == "status":
                            data = message["data"]
                            queue_remaining = (
                                data.get("status", {})
                                .get("exec_info", {})
                                .get("queue_remaining")
                            )
                            if queue_remaining == 0:
                                break
                except websockets.ConnectionClosed:
                    print("Connection closed")
                    break

        # fetching results
        history_result = await self.comfy_api.get_history(prompt_id)
        history = history_result[prompt_id]
        if not output_config:
            result = {"file_list": [], "text_output": []}
            for node_id in history["outputs"]:
                node_output = history["outputs"][node_id]
                if "gifs" in node_output:
                    for gif in node_output["gifs"]:
                        url = await self.get_output_item_url(gif)
                        result["file_list"].append(url)

                if "text" in node_output:
                    for txt in node_output["text"]:
                        result["text_output"].append(txt)

                if "images" in node_output:
                    for img in node_output["images"]:
                        url = await self.get_output_item_url(img)
                        result["file_list"].append(url)
                if 'audio' in node_output:
                    audio = node_output['audio'][0]
                    url = await self.get_output_item_url({
                        "filename": audio,
                        "subfolder": "",
                        "type": "output"
                    })
                    result["file_list"].append(audio)
            return result
        else:
            result = {}
            for output_item in output_config:
                name = output_item["name"]
                type_options = output_item.get("typeOptions")
                if not type_options:
                    continue
                comfyOptions = type_options.get("comfyOptions", {})
                node = comfyOptions.get("node")
                if not node:
                    continue

                is_array = type_options.get("multipleValues", False)
                node_output_data = history["outputs"].get(str(node), {})
                if "gifs" in node_output_data:
                    for gif in node_output_data["gifs"]:
                        url = await self.get_output_item_url(gif)
                        if is_array:
                            if not result.get(name):
                                result[name] = []
                            result[name].append(url)
                        else:
                            result[name] = url
                if "text" in node_output_data:
                    for txt in node_output_data["text"]:
                        if is_array:
                            if not result.get(name):
                                result[name] = []
                            result[name].append(txt)
                        else:
                            result[name] = txt
                if "images" in node_output_data:
                    for img in node_output_data["images"]:
                        url = await self.get_output_item_url(img)
                        if is_array:
                            if not result.get(name):
                                result[name] = []
                            result[name].append(url)
                        else:
                            result[name] = url
                if "audio" in node_output_data:
                    audio = node_output_data["audio"][0]
                    url = await self.get_output_item_url({
                        "filename": audio,
                        "subfolder": "",
                        "type": "output"
                    })
                    if is_array:
                        if not result.get(name):
                            result[name] = []
                        result[name].append(url)
                    else:
                        result[name] = url
            return result

    async def get_custom_nodes_status(self, workflow_json):
        mappings = await self.comfy_api.get_node_mapping_list()
        custom_node_list = await self.comfy_api.get_all_custom_node_list()
        data = custom_node_list["custom_nodes"]

        # Build regex->url map
        regex_to_url = [
            {"regex": re.compile(item["nodename_pattern"]), "url": item["files"][0]}
            for item in data
            if item.get("nodename_pattern")
        ]

        # Build name->url map
        name_to_url = {
            name: url for url, names in mappings.items() for name in names[0]
        }

        registered_nodes = await self.comfy_api.get_registered_nodes()

        missing_nodes = set()
        installed_nodes = set()
        nodes = workflow_json.get("nodes", [])

        for node in nodes:
            node_type = node.get("type", "")
            if node_type.startswith("workflow/"):
                continue

            if node_type not in registered_nodes:
                url = name_to_url.get(node_type.strip(), "")
                if url:
                    missing_nodes.add(url)
                else:
                    for regex_item in regex_to_url:
                        if regex_item["regex"].search(node_type):
                            missing_nodes.add(regex_item["url"])
            else:
                installed_nodes.add(node_type)

        unresolved_nodes = []  # not yet implemented in comfy

        for node_type in unresolved_nodes:
            url = name_to_url.get(node_type, "")
            if url:
                missing_nodes.add(url)

        def get_node_info(node_type):
            url = name_to_url.get(node_type)
            if url:
                return next(
                    (node for node in data if url in node.get("files", [])), None
                )

        uninstalled_nodes = [
            node
            for node in data
            if any(file in missing_nodes for file in node.get("files", []))
        ]
        installed_nodes = [get_node_info(node_type) for node_type in installed_nodes]
        installed_nodes = [node for node in installed_nodes if node]
        return uninstalled_nodes + installed_nodes

    async def get_models_status(self, workflow_api_json):
        self.model_downloader.load_comfy_models()
        all_models = []
        for node in workflow_api_json:
            if "inputs" in workflow_api_json[node]:
                for input in workflow_api_json[node]["inputs"].values():
                    if (
                        isinstance(input, str)
                        and any(input.endswith(ft) for ft in MODEL_FILETYPES)
                        and not any(input.endswith(m) for m in OPTIONAL_MODELS)
                    ):
                        if input not in all_models:
                            all_models.append(input)
        uninstalled_models = []
        for model in all_models:
            if not search_model(model) and model not in uninstalled_models:
                uninstalled_models.append(model)
        return [
            {
                "name": model,
                "installed": "True" if model not in uninstalled_models else "False",
            }
            for model in all_models
        ]

    async def download_models(self, workflow_api_json) -> dict:
        models_downloaded = False
        models = await self.get_models_status(workflow_api_json)
        uninstalled_models = [
            model for model in models if model["installed"] == "False"
        ]
        if len(uninstalled_models) > 0:
            logger.info(f"Models need to download: {uninstalled_models}")
        for model in uninstalled_models:
            status, similar_models, file_status = (
                await self.model_downloader.download_model(model)
            )
            if file_status == FileStatus.NEW_DOWNLOAD.value:
                models_downloaded = True

        return models_downloaded

    async def download_custom_nodes(self, workflow_json) -> dict:
        nodes_installed = False
        # installing missing nodes
        nodes_status = await self.get_custom_nodes_status(workflow_json)
        uninstalled_nodes = [
            node for node in nodes_status if node["installed"] == "False"
        ]
        if len(uninstalled_nodes):
            logger.info(
                f"Installing {len(uninstalled_nodes)} custom nodes"
            )
        for node in uninstalled_nodes:
            logger.info(f"Installing {node['title']}")
            if node["installed"] in ["False", False]:
                status = await self.comfy_api.install_custom_node(node)
                nodes_installed = True
                if status != {}:
                    logger.info("Failed to install custom node ", node["title"])

        return nodes_installed

    async def get_output_item_url(self, file):
        s3_enabled = False
        if os.path.exists(s3_config_file):
            try:
                with open(s3_config_file, "r", encoding="utf-8") as f:
                    s3_config = json.load(f)
                    s3_enabled = s3_config.get("enabled")
            except Exception as e:
                logger.warning("Load s3 config failed: ", str(e))
        filename, subfolder, type = file["filename"], file["subfolder"], file["type"]
        if s3_enabled:
            endpoint_url = s3_config.get("endpoint_url")
            aws_access_key_id = s3_config.get("aws_access_key_id")
            aws_secret_access_key = s3_config.get("aws_secret_access_key")
            region_name = s3_config.get("region_name")
            addressing_style = s3_config.get("addressing_style", "auto")
            bucket = s3_config.get("bucket")
            public_access_url = s3_config.get("public_access_url")
            key = f'artworks/comfyui/{uuid.uuid1().hex}.{filename.split(".")[-1]}'
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name,
                config=Config(s3={"addressing_style": addressing_style}),
            )
            if type == "temp":
                api_client = BaseAPI(f"http://127.0.0.1:{APP_PORT}")
                tmp_url = f"/view?filename={filename}&subfolder={subfolder}&type=temp"
                file_bytes = await api_client.http_get_bytes(tmp_url)
                logger.info(f"Uploading {tmp_url} to s3")
                s3.put_object(Bucket=bucket, Key=key, Body=file_bytes)
                return f"{public_access_url}/{key}"
            else:
                local_path = os.path.join(output_path, subfolder, filename)
                logger.info(f"Uploading {local_path} to s3")
                with open(local_path, "rb") as file:
                    file_bytes = file.read()
                    s3.put_object(Bucket=bucket, Key=key, Body=file_bytes)
                    return f"{public_access_url}/{key}"
        else:
            return f"http://127.0.0.1:{APP_PORT}/view?filename={filename}&subfolder={subfolder}&type=temp"

    async def infer_dependencies(self, workflow_json, workflow_api_json):
        nodes = await self.get_custom_nodes_status(workflow_json)
        models = await self.get_models_status(workflow_api_json)
        return {"nodes": nodes, "models": models}

    async def auto_install_missing_nodes(self, workflow_json):
        nodes = await self.get_custom_nodes_status(workflow_json)
        uninstalled_nodes = [node for node in nodes if node["installed"] == "False"]
        installed_new_node = False
        for node in uninstalled_nodes:
            try:
                await self.comfy_api.install_custom_node(node)
                installed_new_node = True
            except Exception as e:
                logger.error(f"Installed comfyui node {node} failed: {str(e)}")

        if installed_new_node:
            await self.comfy_api.reboot()

    def download_and_replace_value(self, workflow_api_json, node_id, value):
        if not isinstance(value, str) or not (
            value.startswith("http://") or value.startswith("https://")
        ):
            return value

        file_extension = value.split("?")[0].split(".")[-1]
        if not file_extension:
            return value
        file_filename = str(uuid.uuid4()) + "." + file_extension
        file_path = os.path.join("./input/", file_filename)
        download_file_to(value, file_path)
        node_detail = workflow_api_json.get(node_id, {})
        if node_detail.get("class_type") == "VHS_LoadAudio":
            return file_path
        else:
            return file_filename
        
    def generate_seed():
        return random.randint(0, 2**32 - 1)  # 生成32位正整数的随机 seed

    async def predict(
        self,
        workflow_json,
        workflow_api_json,
        input_data={},
        input_config={},
        output_config=None,
    ):
        # download custom nodes
        node_installed = await self.download_custom_nodes(workflow_json)

        # download models if not already present
        model_downloaded = await self.download_models(workflow_api_json)

        # restart the server if custom nodes or models are installed
        if node_installed or model_downloaded:
            logger.info("Restarting the server")
            await self.comfy_api.reboot()

        for node_id, node_data in workflow_api_json.items():
            for input_key in node_data['inputs'].items():
                if input_key == "seed":
                    workflow_api_json[str(node_id)]["inputs"][input_key] = self.generate_seed()

        if input_config:
            for key, value in input_data.items():
                input_items = [item for item in input_config if item["name"] == key]
                if len(input_items) == 0:
                    continue
                input_item = input_items[0]
                type_options = input_item.get("typeOptions", {})
                comfy_options = type_options.get("comfyOptions", {})
                
                if isinstance(comfy_options, list):
                    for comfy_options_item in comfy_options:
                        node_id, key = comfy_options_item.get("node"), comfy_options_item.get("key")
                        if node_id and key:
                            value = self.download_and_replace_value(
                                workflow_api_json, node_id, value
                            )
                            if str(node_id) in workflow_api_json:
                                workflow_api_json[str(node_id)]["inputs"][key] = value
                else:
                    node_id, key = comfy_options.get("node"), comfy_options.get("key")
                    if node_id and key:
                        value = self.download_and_replace_value(
                            workflow_api_json, node_id, value
                        )
                        if str(node_id) in workflow_api_json:
                            workflow_api_json[str(node_id)]["inputs"][key] = value
        else:
            for node_id, values in input_data.items():
                if node_id in workflow_api_json:
                    for key, value in values.items():
                        value = self.download_and_replace_value(
                            workflow_api_json, node_id, value
                        )
                        workflow_api_json[node_id]["inputs"][key] = value

        # get the result
        logger.info("Generating output please wait ...")
        output = await self.run_prompt(workflow_api_json, output_config)
        logger.info(f"Output: {output}")
        return output

import json
import os
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
from .methods import ComfyMethod
from .common import (
    copy_files,
    find_file_in_directory,
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

    async def run_prompt(self, prompt, output_node_ids):
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
                        logger.info(f"Ws received: {message}")
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
        output_list = {"file_list": [], "text_output": []}
        output_node_ids = [str(id) for id in output_node_ids] if output_node_ids else []
        for node_id in history["outputs"]:
            if (
                output_node_ids and len(output_node_ids) and node_id in output_node_ids
            ) or not output_node_ids:
                node_output = history["outputs"][node_id]
                if "gifs" in node_output:
                    for gif in node_output["gifs"]:
                        output_list["file_list"].append(gif)

                if "text" in node_output:
                    for txt in node_output["text"]:
                        output_list["text_output"].append(txt)

                if "images" in node_output:
                    for img in node_output["images"]:
                        output_list["file_list"].append(img)

        return output_list

    async def filter_missing_node(self, workflow):
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
        nodes = [node for _, node in workflow.items()]

        for node in nodes:
            node_type = node.get("class_type", "")
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

        unresolved_nodes = []  # not yet implemented in comfy

        for node_type in unresolved_nodes:
            url = name_to_url.get(node_type, "")
            if url:
                missing_nodes.add(url)

        ans = [
            node
            for node in data
            if any(file in missing_nodes for file in node.get("files", []))
        ]
        # print("********* missing nodes found: ", ans)
        return ans

    async def download_models(
        self, workflow, extra_models_list, ignore_model_list=[]
    ) -> dict:
        models_downloaded = False
        self.model_downloader.load_comfy_models()
        models_to_download = []

        for node in workflow:
            if "inputs" in workflow[node]:
                for input in workflow[node]["inputs"].values():
                    if (
                        isinstance(input, str)
                        and any(input.endswith(ft) for ft in MODEL_FILETYPES)
                        and not any(input.endswith(m) for m in OPTIONAL_MODELS)
                    ):
                        models_to_download.append(input)

        # filtering ignored models
        m_l = []
        ignored_models_found = []
        ignored_model_names_map = {m["filename"]: m for m in ignore_model_list}
        for m in models_to_download:
            if m in ignored_model_names_map:
                ignored_models_found.append(ignored_model_names_map[m])
            else:
                m_l.append(m)
        models_to_download = m_l
        models_not_found = []
        for m in ignored_models_found:
            if "filepath" in m and m["filepath"] and not os.path.exists(m["filepath"]):
                models_not_found.append({"model": m["filename"], "similar_models": []})
            else:
                logger.info(f"Ignoring model {m['filename']}")
        m_l = []
        for model in models_to_download:
            if not search_model(model):
                m_l.append(model)
        models_to_download = m_l

        if len(models_to_download) > 0:
            logger.info(f"Models need to download: {models_downloaded}")
        for model in models_to_download:
            status, similar_models, file_status = (
                await self.model_downloader.download_model(model)
            )
            if not status:
                models_not_found.append(
                    {"model": model, "similar_models": similar_models}
                )
            elif file_status == FileStatus.NEW_DOWNLOAD.value:
                models_downloaded = True

        # downloading extra models
        for model in extra_models_list:
            status, file_status = await self.model_downloader.download_file(
                model["filename"], model["url"], model["dest"]
            )
            if status:
                models_downloaded = (
                    True if file_status == FileStatus.NEW_DOWNLOAD.value else False
                )
                for m in models_not_found:
                    if m["model"] == model["filename"]:
                        models_not_found.remove(m)
                        break

        # checking if models_not_found are already inside comfy
        for model in models_not_found:
            if search_model(model["model"].split("/")[-1]):
                models_not_found.remove(model)

        return {
            "data": {
                "models_not_found": models_not_found,
                "models_downloaded": models_downloaded,
            },
            "message": "model(s) not found" if len(models_not_found) else "",
            "status": False if len(models_not_found) else True,
        }

    async def download_custom_nodes(self, workflow, extra_node_urls) -> dict:
        nodes_installed = False
        # installing missing nodes
        missing_nodes = await self.filter_missing_node(workflow)
        if len(missing_nodes):
            logger.info(f"Installing {len(missing_nodes)} custom nodes")
        for node in missing_nodes:
            logger.info(f"Installing {node['title']}")
            if node["installed"] in ["False", False]:
                nodes_installed = True
                status = await self.comfy_api.install_custom_node(node)
                if status != {}:
                    logger.info("Failed to install custom node ", node["title"])

        # installing custom git repos
        if len(extra_node_urls):
            custom_node_list = await self.comfy_api.get_all_custom_node_list()
            custom_node_list = custom_node_list["custom_nodes"]
            url_node_map = {}
            for node in custom_node_list:
                if node["reference"] not in url_node_map:
                    url_node_map[node["reference"]] = [node]
                else:
                    url_node_map[node["reference"]].append(node)

            for git_url in extra_node_urls:
                nodes_to_install = []
                if git_url in url_node_map:
                    for node in url_node_map[git_url]:
                        nodes_to_install.append(node)
                else:
                    node = {
                        "author": "",
                        "title": "",
                        "reference": git_url,
                        "files": [git_url],
                        "install_type": "git-clone",
                        "description": "",
                        "installed": "False",
                    }
                    nodes_to_install.append(node)

                for n in nodes_to_install:
                    nodes_installed = True
                    status = await self.comfy_api.install_custom_node(n)
                    if status != {}:
                        logger.info("Failed to install custom node ", n["title"])

        return {
            "data": {"nodes_installed": nodes_installed},
            "message": "",
            "status": True,
        }

    def load_workflow(self, workflow_input):
        if os.path.exists(workflow_input):
            try:
                with open(workflow_input, "r", encoding="utf-8") as file:
                    workflow_input = json.load(file)

            except Exception as e:
                logger.info("Exception: ", str(e))
                return None
        else:
            workflow_input = json.loads(workflow_input)

        return workflow_input if ComfyMethod.is_api_json(workflow_input) else None

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

    async def predict(
        self,
        workflow_input,
        input_data={},
        file_path_list=[],
        extra_models_list=[],
        extra_node_urls=[],
        output_node_ids=None,
        ignore_model_list=[],
    ):
        """
        workflow_input:                 API json of the workflow. Can be a filepath or str
        file_path_list:                 files to copy inside the '/input' folder which are being used in the workflow
        extra_models_list:              extra models to be downloaded
        extra_node_urls:                extra nodes to be downloaded
        stop_server_after_completion:   stop server as soon as inference completes (or fails)
        clear_comfy_logs:               clears the temp comfy logs after every inference
        output_folder:                  for storing inference output
        output_node_ids:                nodes to look in for the output
        ignore_model_list:                  these models won't be downloaded (in cases where these are manually placed)
        """
        # TODO: add support for image and normal json files
        workflow = self.load_workflow(workflow_input)
        if not workflow:
            logger.error("Invalid workflow file")
            raise Exception("Invalid workflow")

        # download custom nodes
        res_custom_nodes = await self.download_custom_nodes(workflow, extra_node_urls)
        if not res_custom_nodes["status"]:
            logger.info(res_custom_nodes["message"])
            return

        # download models if not already present
        res_models = await self.download_models(
            workflow, extra_models_list, ignore_model_list
        )
        if not res_models["status"]:
            logger.info(res_models["message"])
            if len(res_models["data"]["models_not_found"]):
                logger.info(
                    "Please provide custom model urls for the models listed below or modify the workflow json to one of the alternative models listed"
                )
                for model in res_models["data"]["models_not_found"]:
                    print("Model: ", model["model"])
                    print("Alternatives: ")
                    if len(model["similar_models"]):
                        for alternative in model["similar_models"]:
                            print(" - ", alternative)
                    else:
                        print(" - None")
                    print("---------------------------")
            return

        # restart the server if custom nodes or models are installed
        if (
            res_custom_nodes["data"]["nodes_installed"]
            or res_models["data"]["models_downloaded"]
        ):
            logger.info("Restarting the server")
            await self.comfy_api.reboot()

        if len(file_path_list):
            for filepath in file_path_list:
                if isinstance(filepath, str):
                    filepath, dest_path = filepath, "./input/"
                else:
                    filepath, dest_path = (
                        filepath["filepath"],
                        "./input/" + filepath["dest_folder"] + "/",
                    )
                copy_files(filepath, dest_path, overwrite=True)

        # checkpoints, lora, default etc..
        comfy_directory = "./models/"
        comfy_model_folders = [
            folder
            for folder in os.listdir(comfy_directory)
            if os.path.isdir(os.path.join(comfy_directory, folder))
        ]
        # update model paths e.g. 'v3_sd15_sparsectrl_rgb.ckpt' --> 'SD1.5/animatediff/v3_sd15_sparsectrl_rgb.ckpt'
        for node in workflow:
            if "inputs" in workflow[node]:
                for key, input in workflow[node]["inputs"].items():
                    if (
                        isinstance(input, str)
                        and any(input.endswith(ft) for ft in MODEL_FILETYPES)
                        and not any(input.endswith(m) for m in OPTIONAL_MODELS)
                    ):
                        base = None
                        # if os.path.sep in input:
                        base, input = os.path.split(input)
                        model_path_list = find_file_in_directory(comfy_directory, input)
                        if len(model_path_list):
                            # selecting the model_path which has the base, if neither has the base then selecting the first one
                            model_path = model_path_list[0]
                            if base:
                                matching_text_seq = (
                                    ["SD1.5"]
                                    if base in ["SD1.5", "SD1.x"]
                                    else ["SDXL"]
                                )
                                for txt in matching_text_seq:
                                    for p in model_path_list:
                                        if txt in p:
                                            model_path = p
                                            break

                            model_path = model_path.replace(comfy_directory, "")
                            if any(
                                model_path.startswith(folder)
                                for folder in comfy_model_folders
                            ):
                                model_path = model_path.split(os.path.sep, 1)[-1]
                            logger.info(f"Updating {input} to {model_path}")
                            workflow[node]["inputs"][key] = model_path
                    elif input_data and input_data.get(node, {}).get(key):
                        workflow[node]["inputs"][key] = input_data.get(node, {}).get(
                            key
                        )
        # get the result
        logger.info("Generating output please wait ...")
        output = await self.run_prompt(workflow, output_node_ids)
        logger.info(f"Raw Output: {output}")
        file_list = []
        for file in output["file_list"]:
            url = await self.get_output_item_url(file)
            file_list.append(url)
        output["file_list"] = file_list
        return output

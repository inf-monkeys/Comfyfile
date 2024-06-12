import os
import subprocess
import shutil
import zipfile
from loguru import logger
import tarfile
import json
from .runner import ComfyRunner
import json
import requests
from tqdm import tqdm
from .common import search_model
import folder_paths
from torchvision.datasets.utils import download_url as torchvision_download_url
from enum import Enum
from typing import Any

# paths
comfyui_monkeys_path = os.path.dirname(__file__)
comfy_path = os.path.dirname(folder_paths.__file__)
custom_nodes_path = os.path.join(comfy_path, "custom_nodes")
js_path = os.path.join(comfy_path, "web", "extensions")
models_path = os.path.join(comfy_path, "models")
input_path = os.path.join(comfy_path, "input")


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

class UniversalEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__  # 将对象转换为字典
        return super().default(obj)  # 调用默认的实现


class Stage:
    def __init__(self, name):
        self.name = name
        self.commands = []

    def add_command(self, command):
        self.commands.append(command)


class ComfyuiPlugin:
    def __init__(self, url: str):
        self.url = url

    def serialize(self):
        return {"url": self.url}


class ComfyuiModel:
    def __init__(self, name: str, url: str, path: str):
        self.name = name
        self.url = url
        self.path = path

    def serialize(self):
        return {"name": self.name, "url": self.url, "path": self.path}

class ComfyfileCommandType(Enum):
    MODEL = 'MODEL'
    PLUGIN = 'PLUGIN'
    SCRIPT = 'SCRIPT'
    RUN = 'RUN'
    COPY = 'COPY'

class ComfyfileExecutionStep:
    def __init__(self, command_type: ComfyfileCommandType, command_data: Any):
        self.command_type = command_type
        self.command_data = command_data
        
    def serialize(self):
        return {
            "command_type": self.command_type.value,
            "command_data": json.dumps(self.command_data, cls=UniversalEncoder)
        }

class ComfyfileApp:
    def __init__(
        self,
        appName: str,
        displayName: str,
        description: str,
        homepage: str,
        plugins: list[ComfyuiPlugin],
        models: list[ComfyuiModel],
        runs: list[str],
        scripts: list[str],
        workflow: dict,
        workflowApi: dict,
        tags: list,
        restEndpoint: dict,
        steps: list[ComfyfileExecutionStep]
    ):
        self.appName = appName
        self.displayName = displayName
        self.description = description
        self.homepage = homepage
        self.plugins = plugins
        self.models = models
        self.workflow = workflow
        self.workflowApi = workflowApi
        self.tags = tags
        self.scripts = scripts
        self.restEndpoint = restEndpoint
        self.steps = steps
        self.runs = runs

    def serialize(self):
        return {
            "appName": self.appName,
            "displayName": self.displayName,
            "description": self.description,
            "homepage": self.homepage,
            "plugins": [plugin.serialize() for plugin in self.plugins],
            "models": [model.serialize() for model in self.models],
            "workflow": self.workflow,
            "workflowApi": self.workflowApi,
            "tags": self.tags,
            "restEndpoint": self.restEndpoint,
            "scripts": self.scripts,
            "steps": [step.serialize() for step in self.steps],
            "runs": self.runs
        }


class ComfyfileExecutor:
    def __init__(self, context_directory, working_directory):
        self.context_directory = context_directory
        self.working_directory = working_directory
        os.makedirs(self.working_directory, exist_ok=True)

    def download_file(self, path, url):
        logger.info(f"Downloading {url} to {path}")
        # download_file_by_wget(url, dest_path=f"{dest}/{filename}")
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get("content-length", 0))
        progress_bar = tqdm(total=total_size, unit="B", unit_scale=True)
        with open(path, "wb") as f:
            for data in response.iter_content(chunk_size=8192):
                if data:
                    f.write(data)
                progress_bar.update(len(data))

    def execute_command(self, command):
        subprocess.run(command, shell=True, check=True, cwd=self.working_directory)

    def handle_plugin(self, url):
        repo_name = url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(self.working_directory, "custom_nodes", repo_name)
        if not os.path.exists(repo_path):
            self.execute_command(f"git clone {url} {repo_path}")

    def handle_run(self, script):
        self.execute_command(script)

    def handle_script(self, script_file):
        script_file = os.path.join(self.context_directory, script_file)
        if not os.path.exists(script_file):
            raise Exception(f"Script file {script_file} not exists")

        with open(script_file, "r", encoding="utf-8") as f:
            script_content = f.read()
            self.execute_command(script_content)

    def handle_model(self, model_path, model_url):
        model_path = os.path.join(comfy_path, model_path)
        if os.path.exists(model_path):
            logger.info(f"Model {model_path} exists, skipping")
            return

        model_path_folder = os.path.dirname(model_path)
        os.makedirs(model_path_folder, exist_ok=True)

        if model_url.endswith(".zip"):
            zip_model_file = model_path + ".zip"
            self.download_file(zip_model_file, model_url)
            with zipfile.ZipFile(zip_model_file, "r") as zip_ref:
                zip_ref.extractall(model_path_folder)
            os.remove(zip_model_file)
        elif model_url.endswith(".tar"):
            tar_model_file = model_path + ".tar"
            self.download_file(tar_model_file, model_url)
            with tarfile.open(tar_model_file, "r") as tar_ref:
                tar_ref.extractall(model_path_folder)
            os.remove(tar_model_file)
        else:
            torchvision_download_url(
                model_url, model_path_folder, os.path.basename(model_path)
            )

    def handle_copy(self, src, dest):
        full_src = os.path.join(self.context_directory, src)
        full_dest = os.path.join(self.working_directory, dest)
        full_dest_parent = os.path.dirname(full_dest)
        os.makedirs(full_dest_parent, exist_ok=True)
        if os.path.exists(full_src):
            if os.path.isdir(full_src):
                shutil.copytree(full_src, full_dest, dirs_exist_ok=True)
            else:
                shutil.copy2(full_src, full_dest)
        else:
            raise FileNotFoundError(f"Source path does not exist: {full_src}")

    def check_model(self, model_path: str):
        model_name = model_path.split("/")[-1]
        return search_model(model_name)

    async def process_comfyfile_apps(self, comfyfile_apps: list[ComfyfileApp]):
        comfyfile_app = comfyfile_apps[0]
        for step in comfyfile_app.steps:
            if step.command_type == ComfyfileCommandType.PLUGIN:
                plugin = step.command_data
                plugin_url = plugin.url
                if plugin_url == "AUTO_INFER_FROM_WORKFLOW_JSON":
                    logger.info("Auto infer missing nodes from workflow.json")
                    runner = ComfyRunner()
                    await runner.auto_install_missing_nodes(comfyfile_app.workflow)
                else:
                    self.handle_plugin(plugin_url)
            elif step.command_type == ComfyfileCommandType.MODEL:
                model = step.command_data
                self.handle_model(model.path, model.url)
            elif step.command_type == ComfyfileCommandType.RUN:
                script = step.command_data
                self.handle_run(script)
            elif step.command_type == ComfyfileCommandType.SCRIPT:
                script = step.command_data
                self.handle_script(script)
            elif step.command_type == ComfyfileCommandType.COPY:
                src, dest = step.command_data
                self.handle_copy(src, dest)

        # build_stage = comfyfile.stages["build"]
        # AUTO_INFER_FROM_WORKFLOW_JSON = False
        # if build_stage:
        #     for command in build_stage.commands:
        #         if command.startswith("PLUGIN"):
        #             _, url = command.split(maxsplit=1)
        #             if url == "AUTO_INFER_FROM_WORKFLOW_JSON":
        #                 AUTO_INFER_FROM_WORKFLOW_JSON = True
        #             else:
        #                 self.handle_plugin(url)
        #         elif command.startswith("MODEL"):
        #             _, model_info = command.split(maxsplit=1)
        #             model_path, model_url = model_info.split()
        #             self.handle_model(model_path, model_url)
        #         elif command.startswith("COPY"):
        #             _, paths = command.split(maxsplit=1)
        #             src, dest = paths.split()
        #             self.handle_copy(src, dest)
        #         elif command.startswith("RUN"):
        #             _, script = command.split(maxsplit=1)
        #             self.handle_run(script)
        #         elif command.startswith("SCRIPT"):
        #             _, script_file = command.split(maxsplit=1)
        #             self.handle_script(script_file)
        #         else:
        #             raise ValueError(f"Unknown command: {command}")

        # serve_stage = comfyfile.stages["serve"]
        # if serve_stage:
        #     app_name_command = next(
        #         (
        #             command
        #             for command in serve_stage.commands
        #             if command.startswith("APP_NAME")
        #         ),
        #         None,
        #     )
        #     if not app_name_command:
        #         raise ValueError("APP_NAME is required in the serve stage")
        #     app_name = app_name_command.split(maxsplit=1)[1]
        #     other_commands = [
        #         command
        #         for command in serve_stage.commands
        #         if not command.startswith("APP_NAME")
        #     ]
        #     for command in other_commands:
        #         if command.startswith("WORKFLOW_API"):
        #             _, src = command.split(maxsplit=1)
        #             self.handle_workflow_api(app_name, src)
        #         elif command.startswith("WORKFLOW"):
        #             _, src = command.split(maxsplit=1)
        #             if AUTO_INFER_FROM_WORKFLOW_JSON:
        #                 logger.info("Auto infer missing nodes from workflow.json")
        #                 full_src = os.path.join(self.context_directory, src)
        #                 with open(full_src, "r", encoding="utf-8") as f:
        #                     workflow_json = json.loads(f.read())
        #                     runner = ComfyRunner()
        #                     await runner.auto_install_missing_nodes(workflow_json)
        #             self.handle_workflow(app_name, src)
        #         elif command.startswith("REST_ENDPOINT"):
        #             _, src = command.split(maxsplit=1)
        #             self.handle_rest_endpoint(app_name, src)
        #         elif command.startswith("MANIFEST"):
        #             _, src = command.split(maxsplit=1)
        #             self.handle_manifest(app_name, src)


class ComfyfileParser:

    def __init__(self, comfyfile_path: str, context_directory: str):
        self.context_directory = context_directory
        self.comfyfile_path = comfyfile_path
        pass

    def parse_comfyfile(self) -> list[ComfyfileApp]:
        with open(self.comfyfile_path, "r", encoding="utf-8") as file:
            comfyfile = file.read()
        lines = comfyfile.split("\n")
        apps = []
        build_plugins = []
        build_models = []
        build_runs = []
        build_scripts = []
        steps = []
        current_app = None
        for line in lines:
            if line.startswith("STAGE"):
                if "serve" in line:
                    if current_app:
                        apps.append(current_app)
                    current_app = ComfyfileApp(
                        appName="",
                        displayName="",
                        description="",
                        homepage="",
                        plugins=list(build_plugins),
                        models=list(build_models),
                        workflow=None,
                        workflowApi=None,
                        tags=[],
                        restEndpoint=None,
                        scripts=list(build_scripts),
                        runs=list(build_runs),
                        steps=list(steps),
                    )
            elif line.startswith("PLUGIN"):
                plugin = self.__parse_plugin_line(line)
                if current_app:
                    current_app.plugins.append(plugin)
                else:
                    build_plugins.append(plugin)
                steps.append(ComfyfileExecutionStep(ComfyfileCommandType.PLUGIN, plugin))
            elif line.startswith("MODEL"):
                model = self.__parse_model_line(line)
                if current_app:
                    current_app.models.append(model)
                else:
                    build_models.append(model)
                steps.append(ComfyfileExecutionStep(ComfyfileCommandType.MODEL, model))
            elif line.startswith("RUN"):
                command = self.__parse_run_line(line)
                if current_app:
                    current_app.runs.append(command)
                else:
                    build_runs.append(command)
                steps.append(ComfyfileExecutionStep(ComfyfileCommandType.RUN, command))
            elif line.startswith("SCRIPT"):
                script_content = self.__parse_script_line(line)
                if current_app:
                    current_app.scripts.append(script_content)
                else:
                    build_scripts.append(script_content)
                steps.append(ComfyfileExecutionStep(ComfyfileCommandType.SCRIPT, script_content))
            elif line.startswith("COPY"):
                src, dest = self.__parse_copy_line(line)
                steps.append(ComfyfileExecutionStep(ComfyfileCommandType.COPY, (src, dest)))

            elif line.startswith("APP_NAME"):
                _, appName = line.split(" ")
                if current_app:
                    current_app.appName = appName
            elif line.startswith("MANIFEST"):
                manifest = self.__parse_manifest_line(line)
                if current_app:
                    if "appName" in manifest:
                        current_app.appName = manifest["appName"]
                    current_app.displayName = manifest["displayName"]
                    current_app.description = manifest["description"]
                    current_app.homepage = manifest["homepage"]
            elif line.startswith("WORKFLOW_API"):
                workflow_api = self.__parse_workflow_api_line(line)
                if current_app:
                    current_app.workflowApi = workflow_api
            elif line.startswith("WORKFLOW"):
                workflow = self.__parse_workflow_line(line)
                if current_app:
                    current_app.workflow = workflow
            elif line.startswith("REST_ENDPOINT"):
                rest_endpoint = self.__parse_rest_endpoint_line(line)
                if current_app:
                    current_app.restEndpoint = rest_endpoint

        if current_app:
            apps.append(current_app)

        return apps

    def __parse_plugin_line(self, line: str) -> ComfyuiPlugin:
        _, url = line.split(" ")
        return ComfyuiPlugin(url)

    def __parse_model_line(self, line: str) -> ComfyuiModel:
        parts = line.split()
        path = parts[1]
        url = parts[2]
        name = os.path.basename(path)
        return ComfyuiModel(name, url, path)

    def __parse_run_line(self, line: str) -> str:
        script = " ".join(line.split()[1:])
        return script

    def __parse_script_line(self, line: str) -> str:
        _, script_file = line.split()
        script_file = os.path.join(self.context_directory, script_file)
        if not os.path.exists(script_file):
            raise Exception(f"Script file {script_file} not exists")
        with open(script_file, "r", encoding="utf-8") as f:
            script_content = f.read()
        return script_content

    def __parse_copy_line(self, line: str) -> tuple:
        _, src, dest = line.split()
        return src, dest

    def __parse_manifest_line(self, line: str) -> dict:
        _, manifest_relative_file = line.split()
        manifest_file = os.path.join(
            self.context_directory, manifest_relative_file.strip()
        )
        if not os.path.exists(manifest_file):
            raise FileNotFoundError(f"Manifest file {manifest_file} not exists")
        with open(manifest_file, "r", encoding="utf-8") as file:
            manifest = json.load(file)
        return manifest

    def __parse_workflow_line(self, line: str) -> dict:
        _, workflow_relative_file = line.split()
        workflow_file = os.path.join(
            self.context_directory, workflow_relative_file.strip()
        )
        if not os.path.exists(workflow_file):
            raise FileNotFoundError(f"Workflow file {workflow_file} not exists")
        with open(workflow_file, "r", encoding="utf-8") as file:
            workflow = json.load(file)
        return workflow

    def __parse_workflow_api_line(self, line: str) -> dict:
        _, workflow_api_relative_file = line.split()
        workflow_api_file = os.path.join(
            self.context_directory, workflow_api_relative_file.strip()
        )
        if not os.path.exists(workflow_api_file):
            raise FileNotFoundError(f"Workflow API file {workflow_api_file} not exists")
        with open(workflow_api_file, "r", encoding="utf-8") as file:
            workflow_api = json.load(file)
        return workflow_api

    def __parse_rest_endpoint_line(self, line: str) -> dict:
        _, rest_endpoint_relative_file = line.split()
        rest_endpoint_file = os.path.join(
            self.context_directory, rest_endpoint_relative_file.strip()
        )
        if not os.path.exists(rest_endpoint_file):
            raise FileNotFoundError(f"Rest endpoint file {rest_endpoint_file} not exists")
        with open(rest_endpoint_file, "r", encoding="utf-8") as file:
            rest_endpoint = json.load(file)
        return rest_endpoint

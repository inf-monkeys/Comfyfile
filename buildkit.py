import argparse
import os
import subprocess
import shutil
import uuid
import zipfile
from loguru import logger
import tarfile

import requests
from tqdm import tqdm
from .common import search_model
import folder_paths
from torchvision.datasets.utils import download_url as torchvision_download_url

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


class Stage:
    def __init__(self, name):
        self.name = name
        self.commands = []

    def add_command(self, command):
        self.commands.append(command)


class Comfyfile:
    def __init__(self):
        self.stages = {"build": Stage("build"), "serve": Stage("serve")}

    def add_command_to_stage(self, stage_name, command):
        if stage_name in self.stages:
            self.stages[stage_name].add_command(command)
        else:
            raise ValueError(f"Unknown stage: {stage_name}")

    def parse_comfyfile(self, comfyfile_path):
        with open(comfyfile_path, "r") as f:
            file_content = f.read()
        current_stage = None
        current_command = ""

        for line in file_content.splitlines():
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if line.startswith("STAGE"):
                if current_command:
                    self.add_command_to_stage(current_stage, current_command)
                    current_command = ""
                _, stage_name = line.split()
                current_stage = stage_name
            elif current_stage:
                if line.endswith("\\"):
                    current_command += line[:-1].strip() + " "
                else:
                    current_command += line
                    self.add_command_to_stage(current_stage, current_command)
                    current_command = ""

        if current_command:
            self.add_command_to_stage(current_stage, current_command)

        return self


class Executor:
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

    def handle_workflow(self, app_name, src):
        self.handle_copy(
            src,
            os.path.join("custom_nodes/Comfyfile/apps", app_name, "workflow.json"),
        )

    def handle_workflow_api(self, app_name, src):
        self.handle_copy(
            src,
            os.path.join("custom_nodes/Comfyfile/apps", app_name, "workflow_api.json"),
        )

    def handle_rest_endpoint(self, app_name, src):
        self.handle_copy(
            src,
            os.path.join("custom_nodes/Comfyfile/apps", app_name, "rest_endpoint.json"),
        )

    def handle_manifest(self, app_name, src):
        self.handle_copy(
            src,
            os.path.join("custom_nodes/Comfyfile/apps", app_name, "manifest.json"),
        )

    def check_plugin(self, url: str):
        repo_name = url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(custom_nodes_path, repo_name)
        return os.path.exists(repo_path)

    def check_model(self, model_path: str):
        model_name = model_path.split("/")[-1]
        return search_model(model_name)

    def check_dependencies(self, comfyfile: Comfyfile):
        dependencies = []
        build_stage = comfyfile.stages["build"]
        if build_stage:
            for command in build_stage.commands:
                if command.startswith("PLUGIN"):
                    _, url = command.split(maxsplit=1)
                    installed = self.check_plugin(url)
                    dependencies.append(
                        {
                            "type": "node",
                            "name": url.split("/")[-1].replace(".git", ""),
                            "url": url,
                            "installed": installed
                        }
                    )
                elif command.startswith("MODEL"):
                    _, model_info = command.split(maxsplit=1)
                    model_path, _ = model_info.split()
                    self.check_model(model_path)

    def process_comfyfile(self, comfyfile: Comfyfile):
        build_stage = comfyfile.stages["build"]
        if build_stage:
            for command in build_stage.commands:
                if command.startswith("PLUGIN"):
                    _, url = command.split(maxsplit=1)
                    self.handle_plugin(url)
                elif command.startswith("MODEL"):
                    _, model_info = command.split(maxsplit=1)
                    model_path, model_url = model_info.split()
                    self.handle_model(model_path, model_url)
                elif command.startswith("COPY"):
                    _, paths = command.split(maxsplit=1)
                    src, dest = paths.split()
                    self.handle_copy(src, dest)
                elif command.startswith("RUN"):
                    _, script = command.split(maxsplit=1)
                    self.handle_run(script)
                elif command.startswith("SCRIPT"):
                    _, script_file = command.split(maxsplit=1)
                    self.handle_script(script_file)

        serve_stage = comfyfile.stages["serve"]
        if serve_stage:
            app_name_command = next(
                (
                    command
                    for command in serve_stage.commands
                    if command.startswith("APP_NAME")
                ),
                None,
            )
            if not app_name_command:
                raise ValueError("APP_NAME is required in the serve stage")
            app_name = app_name_command.split(maxsplit=1)[1]
            other_commands = [
                command
                for command in serve_stage.commands
                if not command.startswith("APP_NAME")
            ]
            for command in other_commands:
                if command.startswith("WORKFLOW_API"):
                    _, src = command.split(maxsplit=1)
                    self.handle_workflow_api(app_name, src)
                elif command.startswith("WORKFLOW"):
                    _, src = command.split(maxsplit=1)
                    self.handle_workflow(app_name, src)
                elif command.startswith("REST_ENDPOINT"):
                    _, src = command.split(maxsplit=1)
                    self.handle_rest_endpoint(app_name, src)
                elif command.startswith("MANIFEST"):
                    _, src = command.split(maxsplit=1)
                    self.handle_manifest(app_name, src)

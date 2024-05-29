from enum import Enum
import os

import aiohttp
import requests
import tarfile
import zipfile
import json
from tqdm import tqdm
from .constants import COMFY_MODEL_PATH_LIST
from .api import ComfyAPI
from loguru import logger
from .common import fuzzy_text_match, search_model
from comfy.cli_args import args


class FileStatus(Enum):
    NEW_DOWNLOAD = "new_download"
    ALREADY_PRESENT = "already_present"
    UNAVAILABLE = "unavailable"


class FileDownloader:
    def __init__(self):
        pass

    def is_file_downloaded(self, filename, url, dest):
        zip_file = False
        percentage_diff = lambda a, b: int(round(abs(a - b) / b, 2) * 100)
        if url.endswith(".zip") or url.endswith(".tar"):
            # filename = filename + (".zip" if url.endswith(".zip") else ".tar")
            zip_file = True

        dest_path = f"{dest}/{filename}"
        logger.info("checking file: ", dest_path)
        return os.path.exists(dest_path)
        #     downloaded_file_size = os.path.getsize(dest_path)
        #     url_file_size = get_file_size(url)
        #     # NOTE: hackish sol of checking if zip file is downloaded or not (by checking if the extracted file is approximately the same size)
        #     # possible issues 1. partially downloaded zip file 2. new model file with smaller size
        #     return downloaded_file_size == url_file_size if not zip_file else \
        #         percentage_diff(downloaded_file_size, url_file_size) <= 2
        # return False

    async def download_file(self, filename, url, dest):
        os.makedirs(dest, exist_ok=True)

        # checking if the file is already downloaded
        if self.is_file_downloaded(filename, url, dest):
            logger.info(f"{filename} already present")
            return True, FileStatus.ALREADY_PRESENT.value
        else:
            # deleting partial downloads
            if os.path.exists(f"{dest}/{filename}"):
                os.remove(f"{dest}/{filename}")

        # download progress bar
        logger.info(f"Downloading {dest}/{filename} from {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                total_size = int(response.headers.get("content-length", 0))
                progress_bar = tqdm(total=total_size, unit="B", unit_scale=True)

                with open(f"{dest}/{filename}", "wb") as handle:
                    async for data in response.content.iter_chunked(8192):
                        if data:
                            handle.write(data)
                        progress_bar.update(len(data))

        # extract files if the downloaded file is a .zip or .tar
        if url.endswith(".zip") or url.endswith(".tar"):
            new_filename = filename + (".zip" if url.endswith(".zip") else ".tar")
            os.rename(f"{dest}/{filename}", f"{dest}/{new_filename}")
            if url.endswith(".zip"):
                with zipfile.ZipFile(f"{dest}/{new_filename}", "r") as zip_ref:
                    zip_ref.extractall(dest)
            else:
                with tarfile.open(f"{dest}/{new_filename}", "r") as tar_ref:
                    tar_ref.extractall(dest)
            os.remove(f"{dest}/{new_filename}")

        return True, FileStatus.NEW_DOWNLOAD.value


class ModelDownloader(FileDownloader):
    def __init__(self, model_weights_file_path_list, download_similar_model=False):
        super().__init__()
        self.model_download_dict = self.comfy_model_dict = {}
        self.download_similar_model = download_similar_model
        self.comfy_api = ComfyAPI("http://127.0.0.1", args.port)

        # loading local data
        for model_weights_file_path in model_weights_file_path_list:
            with open(model_weights_file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                for model_name in data:
                    # weight files with lower index have preference
                    if model_name not in self.model_download_dict:
                        self.model_download_dict[model_name] = {
                            "url": data[model_name]["url"],
                            "dest": data[model_name]["dest"],
                        }

    def _get_similar_models(self, model_name):
        logger.info("matching model: ", model_name)
        # matching with local data
        model_list = self.model_download_dict.keys()
        similar_models = fuzzy_text_match(model_list, model_name)

        # matching with comfy data
        model_list = self.comfy_model_dict.keys()
        similar_models += fuzzy_text_match(model_list, model_name)

        return similar_models

    def load_comfy_models(self):
        self.comfy_model_dict = {}
        for model_list_path in COMFY_MODEL_PATH_LIST:
            if not os.path.exists(model_list_path):
                logger.info(f"model list path not found - {model_list_path}")
                continue

            with open(model_list_path, "rb") as file:
                model_list = json.load(file)["models"]

            # loading comfy data
            for model in model_list:
                if model["filename"] not in self.comfy_model_dict:
                    self.comfy_model_dict[model["filename"]] = [model]
                else:
                    self.comfy_model_dict[model["filename"]].append(model)

    async def download_model(self, model_name):
        # handling nomenclature like "SD1.5/pytorch_model.bin"
        base, model_name = (
            (model_name.split("/")[0], model_name.split("/")[-1])
            if "/" in model_name
            else ("", model_name)
        )
        file_status = FileStatus.NEW_DOWNLOAD.value

        if model_name in self.model_download_dict:
            _, file_status = await self.download_file(
                filename=model_name,
                url=self.model_download_dict[model_name]["url"],
                dest=self.model_download_dict[model_name]["dest"],
            )

        elif model_name in self.comfy_model_dict:
            for model in self.comfy_model_dict[model_name]:
                if (
                    (base and model["base"] == base)
                    or not base
                    or (
                        base in ["SD1.5", "SD1.x"]
                        and model["base"] in ["SD1.5", "SD1.x"]
                    )
                ):
                    logger.info(f"Downloading {model['filename']} by ComfyUI Manager")
                    file_status = (
                        FileStatus.ALREADY_PRESENT.value
                        if search_model(model["filename"])
                        else FileStatus.NEW_DOWNLOAD.value
                    )
                    await self.comfy_api.install_custom_model(
                        model
                    )  # TODO: remove/streamline api dependency

        else:
            logger.info(f"Model {model_name} not found in model weights")
            similar_models = self._get_similar_models(model_name)
            if self.download_similar_model and len(similar_models):
                pass
            else:
                return (False, similar_models, FileStatus.UNAVAILABLE.value)

        return (True, [], file_status)

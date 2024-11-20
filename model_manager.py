
import hashlib
import json
import os

from loguru import logger
import yaml

from .constants import (
    MODEL_FILETYPES,
    model_config_file
    )


class ComfyfileModelManager:
    def __init__(self):
        pass
  
    def get_extra_model_data(self):
        extra_config_path = "./extra_model_paths.yaml"
        if os.path.exists(extra_config_path):
            with open(extra_config_path, 'r') as file:
                extra_config_data = yaml.safe_load(file)
            return extra_config_data
        else:
            return None
      
    def get_model_list_from_base_path(self, base_path = "./models", type = "internal"):
        result = []
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith(tuple(MODEL_FILETYPES)):
                    file_path = os.path.join(root, file)
                    # 检查是否为软链接
                    if os.path.islink(file_path):
                        file_path = os.path.realpath(file_path)
                    relative_path = os.path.relpath(os.path.join(root, file), base_path)
                    hash_sha256 = hashlib.sha256()
                    chunk_size = 4096
                    try:
                        file_size = os.path.getsize(file_path)
                        with open(file_path, "rb") as f:
                            # 读取文件开头
                            f.seek(0)
                            hash_sha256.update(f.read(chunk_size))
                            
                            # 读取文件中间部分
                            if file_size > 2 * chunk_size:
                                f.seek(file_size // 2)
                                hash_sha256.update(f.read(chunk_size))
                            
                            # 读取文件末尾
                            f.seek(-chunk_size, os.SEEK_END)
                            hash_sha256.update(f.read(chunk_size))
                            result.append({
                                "path": relative_path,
                                "sha256": hash_sha256.hexdigest(),
                                "type": type,
                                "base_path": base_path
                            })
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
        return result
  
    def get_model_list(self):
        result = []
        result += self.get_model_list_from_base_path()
        extra_model_data = self.get_extra_model_data()
        if extra_model_data != None:
            for type, data in extra_model_data.items():
                result += self.get_model_list_from_base_path(data['base_path'], type)
        return result
    
    def get_model_download_path(self):
        extra_model_data = self.get_extra_model_data()
        if extra_model_data != None and os.path.exists(model_config_file):
            try:
                with open(model_config_file, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
                    download_path_type = model_config.get("download_path_type")
                    return extra_model_data[download_path_type]['base_path']
            except Exception as e:
                logger.warning("Load model config failed: ", str(e))
        else:
            return "models"
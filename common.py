import subprocess
import requests
from fuzzywuzzy import process
import os
import shutil
import psutil
import requests
import json
from loguru import logger
from .constants import models_path, custom_nodes_path


def get_file_size(url):
    response = requests.get(url, stream=True)
    try:
        total_size = int(response.headers.get("content-length", 0))
        return total_size
    except Exception as e:
        return None


def fuzzy_text_match(text_list, query, limit=2):
    matches = process.extract(query, text_list, limit=limit)
    return [match for match, score in matches if score > 90]


def is_ignored_file(filename):
    ignore_list = [
        ".DS_Store",
        ".gitignore",
        "_output_images_will_be_put_here",
        "__MACOSX",
    ]
    return any(ignored_file.lower() in filename.lower() for ignored_file in ignore_list)


def copy_files(source_path, destination_path, overwrite=False, delete_original=False):
    os.makedirs(destination_path, exist_ok=True)
    destination_file = os.path.join(destination_path, os.path.basename(source_path))

    if os.path.isdir(source_path):
        res = []
        for file in os.listdir(source_path):
            if not is_ignored_file(
                file
            ):  # not os.path.isdir(os.path.join(source_path, file)) and
                res.append(
                    copy_files(
                        os.path.join(source_path, file),
                        destination_path,
                        overwrite,
                        delete_original,
                    )
                )

        return res
    else:
        if not overwrite and os.path.exists(destination_file):
            base_name, extension = os.path.splitext(os.path.basename(source_path))
            count = 1
            while os.path.exists(
                os.path.join(destination_path, f"{base_name}_{count}{extension}")
            ):
                count += 1
            unique_name = f"{base_name}_{count}{extension}"
            destination_file = os.path.join(destination_path, unique_name)
        else:
            unique_name = os.path.basename(source_path)

        shutil.copy2(source_path, destination_file)
        if delete_original:
            os.remove(source_path)

        return unique_name


def find_process_by_port(port):
    pid = None
    for proc in psutil.process_iter(attrs=["pid", "name", "connections"]):
        try:
            if proc and "connections" in proc.info and proc.info["connections"]:
                for conn in proc.info["connections"]:
                    if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                        logger.info(f"Process {proc.info['pid']} (Port {port})")
                        pid = proc.info["pid"]
                        break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    return pid


def find_file_in_directory(directory, target_file):
    file_list = []
    for root, dirs, files in os.walk(directory):
        if target_file in files:
            file_list.append(os.path.join(root, target_file))

    return file_list


def clear_directory(directory):
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)


# recursively moves up directories till it finds the .git file (root of the repo)
def find_git_root(path):
    if ".git" in os.listdir(path):
        return path

    parent_path = os.path.abspath(os.path.join(path, os.pardir))
    return find_git_root(parent_path)


# hackish sol for checking if a file is already downloaded by the comfy manager
# possible issues
# 1. a different file of same name can be present in some other directory
# 2. file may be corrupted
def search_file(filename, search_directory):
    """
    检查文件是否存在于指定目录及其子目录中。

    参数:
    filename (str): 需要检查的文件名，可以是相对路径如 a.txt 或者 subfolder/a.txt
    search_directory (str): 需要搜索的目录

    返回:
    bool: 文件是否存在
    """
    for root, dirs, files in os.walk(search_directory):
        if filename in files:
            return True
        # 检查相对路径
        filepath = os.path.join(root, filename)
        if os.path.isfile(filepath):
            return True
    return False


def search_model(model_name):
    if search_file(model_name, custom_nodes_path):
        return True
    if search_file(model_name, models_path):
        return True
    return False


def fetch_json(url):
    try:
        # 发送 HTTP GET 请求
        response = requests.get(url)

        # 确认请求成功（状态码为 200）
        response.raise_for_status()

        # 解析 JSON 数据
        json_data = response.json()

        return json_data
    except requests.exceptions.RequestException as e:
        print(f"HTTP 请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"解析 JSON 失败: {e}")
        return None


def download_file_by_wget(url, dest_path):
    """
    下载文件到指定路径

    参数:
    url (str): 文件的URL
    dest_path (str): 保存文件的目标路径

    返回:
    bool: 文件下载是否成功
    """
    try:
        result = subprocess.run(["wget", "-O", dest_path, url], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"下载文件时出错: {e.stderr.decode().strip()}")
        return False


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

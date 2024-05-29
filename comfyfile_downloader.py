import requests
import os
from loguru import logger


def download_file(url, output_path):
    response = requests.get(url)
    with open(output_path, "wb") as file:
        file.write(response.content)
    logger.info(f"Downloaded {url} to {output_path}")


def download_github_directory(repo_url, output_dir):
    # 解析 GitHub 仓库信息
    parts = repo_url.split("/")
    owner = parts[3]
    repo = parts[4]
    branch = parts[6]
    path = "/".join(parts[7:])

    # GitHub API URL
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    )

    # 发送请求
    response = requests.get(api_url)
    if response.status_code == 200:
        contents = response.json()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for item in contents:
            item_path = os.path.join(output_dir, item["name"])
            if item["type"] == "file":
                download_file(item["download_url"], item_path)
            elif item["type"] == "dir":
                download_github_directory(item["html_url"], item_path)
    else:
        logger.error(
            f"Error: Unable to fetch contents from {api_url}, status code: {response.status_code}"
        )
        response.raise_for_status()

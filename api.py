import aiohttp
import requests
from loguru import logger
from urllib.parse import urljoin


class BaseAPI:
    def __init__(self, base_url, auth_token=None):
        self.base_url = base_url
        self.auth_token = auth_token

    def _get_headers(self, content_type="application/json"):
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"  # 添加 Authorization header
        if content_type:
            headers["Content-Type"] = content_type

        return headers

    async def http_get_bytes(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(urljoin(self.base_url, url), headers=self._get_headers(), proxy=None) as response:
                if response.status == 200:
                    image_bytes = await response.read()
                    return image_bytes
                else:
                    print(
                        f"Failed to fetch image from {url}. Status code: {response.status}"
                    )
                    return None

    async def http_get(self, url, params=None):
        async with aiohttp.ClientSession() as session:
            headers = self._get_headers()
            async with session.get(
                url=urljoin(self.base_url, url), params=params, headers=headers, proxy=None
            ) as response:
                data = await response.json()
                return data

    async def http_get_noresult(self, url, params=None):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=urljoin(self.base_url, url), params=params, headers=self._get_headers(), proxy=None
            ) as response:
                pass

    async def http_post(self, url, data={}, file_content=None):
        async with aiohttp.ClientSession() as session:
            if file_content:
                async with session.post(
                    url=urljoin(self.base_url, url),
                    data=data,
                    files=file_content,
                    headers=self._get_headers(None),
                    proxy=None
                ) as response:
                    data = await response.json()
                    return data
            else:
                async with session.post(
                    url=urljoin(self.base_url, url),
                    json=data,
                    headers=self._get_headers(None),
                    proxy=None
                ) as response:
                    data = await response.json()
                    return data

    async def http_post_plaintext(self, url, text):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=urljoin(self.base_url, url),
                data=text,
                headers=self._get_headers("text/plain"),
                proxy=None
            ) as response:
                pass

    def http_put(self, url, data=None):
        res = requests.put(self.base_url + url, json=data, headers=self._get_headers(), proxy=None)
        return res.json()

    def http_delete(self, url, params=None):
        res = requests.delete(
            self.base_url + url, params=params, headers=self._get_headers(), proxy=None
        )
        return res.json()


class ComfyAPI(BaseAPI):
    def __init__(self, server_addr, port, auth_token=None):
        super().__init__(base_url=f"{server_addr}:{port}", auth_token=auth_token)
        self.server_addr = server_addr
        self.port = port

        self._set_urls()

    def _set_urls(self):
        self.SERVER_URL = f"{self.server_addr}:{self.port}"

        self.QUEUE_PROMPT_URL = "/prompt"
        self.HISTORY_URL = "/history"
        self.CUSTOM_NODE_LIST_URL = "/customnode/getlist"
        self.CUSTOM_NODE_URL = (
            "/customnode/"  # mode can be added in front {install, uninstall, update}
        )
        self.CUSTOM_NODE_GIT_URL = (
            "/customnode/install/git_url"
        )
        self.REGISTERED_NODE_LIST_URL = "/object_info"
        self.NODE_MAPPING_LIST_URL = "/customnode/getmappings"
        self.MODEL_LIST_URL = "/externalmodel/getlist"
        self.CUSTOM_MODEL_URL = "/model/"
        self.REBOOT_URL = "/reboot"

    async def get_all_custom_node_list(self):
        res = await self.http_get(self.CUSTOM_NODE_LIST_URL + "?mode=local")
        if "custom_nodes" in res:
            return res["custom_nodes"]
        elif "node_packs" in res:
            # 将 node_packs 对象转换为数组格式以兼容 custom_nodes 的格式
            node_packs = res["node_packs"]
            result = []
            for node_id, node_data in node_packs.items():
                # 创建新对象并添加 id 字段
                node_obj = {"id": node_id}
                # 复制其他属性
                for key, value in node_data.items():
                    node_obj[key] = value
                result.append(node_obj)
            return result
        else:
            return []

    async def get_all_model_list(self):
        res = await self.http_get(self.MODEL_LIST_URL + "?mode=local")
        return res["models"] if "models" in res else []

    async def get_history(self, prompt_id):
        return await self.http_get(self.HISTORY_URL + "/" + str(prompt_id))

    async def install_custom_node(self, node):
        return await self.http_post(self.CUSTOM_NODE_URL + "install", data=node)

    async def install_custom_model(self, model):
        return await self.http_post(self.CUSTOM_MODEL_URL + "install", data=model)

    async def get_node_mapping_list(self):
        return await self.http_get(self.NODE_MAPPING_LIST_URL + "?mode=local")

    async def get_registered_nodes(self):
        return await self.http_get(self.REGISTERED_NODE_LIST_URL)

    async def queue_prompt(self, prompt, client_id):
        p = {"prompt": prompt, "client_id": client_id}
        return await self.http_post(self.QUEUE_PROMPT_URL, data=p)

    async def reboot(self):
        try:
            return await self.http_get_noresult(self.REBOOT_URL)
        except Exception as e:
            return {
                "reboot": True
            }

    async def install_custom_node_by_git_url(self, git_url):
        return await self.http_post_plaintext(self.CUSTOM_NODE_GIT_URL, git_url)

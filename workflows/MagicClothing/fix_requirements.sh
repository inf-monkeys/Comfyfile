#!/bin/bash

# 定义文件路径
file_path="custom_nodes/ComfyUI_MagicClothing/requirements.txt"

# 删除包含特定字符串的行
sed -i '/--extra-index-url https:\/\/download.pytorch.org\/whl\/cu118/d' "$file_path"
sed -i '/torch==2.1.1+cu118/d' "$file_path"
sed -i '/torchvision==0.16.1+cu118/d' "$file_path"

echo "custom_nodes/ComfyUI_MagicClothing/requirements.txt 指定的行已删除。"

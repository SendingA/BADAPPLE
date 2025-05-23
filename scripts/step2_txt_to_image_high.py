#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用 **Automatic1111 WebUI** 的 ``/sdapi/v1/txt2img`` 接口根据 Excel
中的提示词自动批量生成图片，并支持按编号重绘。

这是原 ComfyUI 脚本的 *drop‑in* 替换版：
1. **移除** 了所有 ComfyUI 专用依赖与工作流构建代码；
2. **保留** 了原有的中文注释、终端输出与交互逻辑；
3. 仍然通过读取 ``txt/txt2.xlsx`` 第 **C** 列的非空单元格来获取提示词，
   生成的 PNG 将保存到 ``image/``；参数日志以 JSONL 形式写入 ``temp/params.jsonl``。

运行方式：
>>> python generate_images_webui.py

执行后脚本会先生成所有图片，然后在终端提示：
>>> 请输入需要重绘的图片编号（空格分隔，输入 N 退出）：
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import sys
from typing import Any, Optional

import openpyxl  # pip install openpyxl
import requests  # pip install requests
from tqdm import tqdm  # pip install tqdm

# ---------------------------------------------------------------------------
# 日志与全局常量
# ---------------------------------------------------------------------------
DEBUG: bool = False  # 修改为 True 可开启调试输出
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# WebUI 服务器地址，可通过环境变量覆盖
SERVER_URL: str = os.getenv("WEBUI_SERVER_URL", "http://172.18.36.54:7862").rstrip("/")
TXT2IMG_URL: str = f"{SERVER_URL}/sdapi/v1/txt2img"

CURRENT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_XLSX: str = os.path.join(CURRENT_DIR, "txt", "output.xlsx")
IMAGE_DIR: str = os.path.join(CURRENT_DIR, "image")
PARAMS_LOG: str = os.path.join(CURRENT_DIR, "temp", "params.jsonl")
print(CURRENT_DIR)
# 创建必要目录
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PARAMS_LOG), exist_ok=True)

# ---------------------------------------------------------------------------
# Excel 工具函数
# ---------------------------------------------------------------------------

def get_prompts(path: str) -> list[str]:
    """读取指定 Excel 文件第 C 列中的非空单元格，返回提示词列表。"""

    wb = openpyxl.load_workbook(path)
    sheet = wb.active
    prompts = [cell.value for cell in sheet["C"][1:] if cell.value]
    wb.close()
    return prompts

# ---------------------------------------------------------------------------
# WebUI 相关辅助函数
# ---------------------------------------------------------------------------

def _encode_image_to_base64(path: str) -> str:
    """将本地图片文件编码为 base64 字符串。"""

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def txt2img(payload: dict[str, Any]) -> bytes:
    """调用 WebUI 的 txt2img 接口并返回第一张图片的二进制数据。"""
    resp = requests.post(TXT2IMG_URL, json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("images"):
        raise RuntimeError("WebUI 未返回任何图像！")
    return base64.b64decode(data["images"][0])

# ---------------------------------------------------------------------------
# 核心生成流程
# ---------------------------------------------------------------------------

def run_webui_program(
    prompts_to_redraw: Optional[list[int]] = None,
    extra_params: dict[str, Any] | None = None,
    control_image: str | None = None,
) -> None:
    """批量生成（或重绘）PNG 图片。"""

    prompts = get_prompts(PROMPT_XLSX)

    # 需要处理的索引集合
    indices = (
        prompts_to_redraw
        if prompts_to_redraw is not None
        else list(range(len(prompts)))
    )

    # 默认生成参数，可根据需要修改
    params: dict[str, Any] = {
        "width": 1024,
        "height": 512,
        "steps": 60,
        "sampler_name": "DPM++ 3M SDE",
        "scheduler": "Karras",
        "batch_size": 1,
        "cfg_scale": 13.5,
        "seed": -1,
        "enable_hr": False,
        "hr_scale": 2,
        "hr_upscaler": "Latent",
        "denoising_strength": 0.7,
    }
    if extra_params:
        params.update(extra_params)

    # 读取用户自定义配置（若存在）
    cfg_path = os.path.join(CURRENT_DIR, "config.json")
    user_cfg: dict[str, str] = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
    data = user_cfg.get("data", {})
    negative_prompt: str = data.get("negative_prompt", "")

    # 控制图（如果提供）
    encoded_control_img = _encode_image_to_base64(control_image) if control_image else None
    encoded_regional_img = True

    for idx in tqdm(indices, desc="生成中", unit="张"):
        import re
        prompt_core = prompts[idx]
        positive_prompt = prompt_core

        # Find the first occurrence of "(number..." in the prompt
        print(f"提示词：{prompt_core}")
        match = re.search(r'\(\d+[^,)]*', prompt_core)
        if match:
            pattern_start = match.group(0)
            number_match = re.search(r'\d+', pattern_start)
            num_of_characters_pattern = int(number_match.group()) if number_match else None
        else:
            num_of_characters_pattern = None

        if num_of_characters_pattern and num_of_characters_pattern >= 2:
            ratio = ",".join(["1"] * num_of_characters_pattern)
        else:
            ratio = "1"
        # 构建 payload
        payload: dict[str, Any] = {
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            **{k: params[k] for k in (
                "width",
                "height",
                "steps",
                "sampler_name",
                "scheduler",
                "batch_size",
                "cfg_scale",
                "seed",
                "enable_hr",
                "hr_scale",
                "hr_upscaler",
                "denoising_strength",
            )},
        }

        if encoded_control_img:
            payload.setdefault("alwayson_scripts", {}).update(
                {
                    "controlnet": {
                        "args": [
                            {
                                "enabled": True,
                                "image": encoded_control_img,
                                "module": "ip-adapter-auto",
                                "model": "ip-adapter_sd15_plus [32cd8f7f]",
                            }
                        ]
                    },
                }
            )
        if encoded_regional_img:
            payload.setdefault("alwayson_scripts", {}).update(
                {
                    "Regional Prompter": {
                        "args": [
                            True,                  # 1  Active
                            False,                 # 2  debug
                            "Matrix",              # 3  Mode
                            "Vertical",            # 4  Mode (Matrix)
                            "Mask",                # 5  Mode (Mask)
                            "Prompt",              # 6  Mode (Prompt)
                            ratio,               # 7  Ratios
                            "",                    # 8  Base Ratios
                            False,                 # 9  Use Base
                            True,                 # 10 Use Common
                            False,                 # 11 Use Neg-Common
                            "Attention",           # 12 Calcmode
                            False,                 # 13 Not Change AND
                            "0",                   # 14 LoRA Textencoder
                            "0",                   # 15 LoRA U-Net
                            "0",                   # 16 Threshold
                            "",                    # 17 Mask (图片路径)
                            "0",                   # 18 LoRA stop step
                            "0",                   # 19 LoRA Hires stop step
                            False                  # 20 flip
                        ]
                    }}
            )
        try:
            img_bytes = txt2img(payload)
        except Exception as exc:
            logging.error("生成失败（#%d）：%s", idx + 1, exc)
            continue

        out_name = f"output_{idx + 1}.png"
        out_path = os.path.join(IMAGE_DIR, out_name)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        logging.info("图片已保存 → %s", out_path)

        # 记录参数（JSONL）
        with open(PARAMS_LOG, "a", encoding="utf-8") as fp:
            json.dump({out_name: payload}, fp, ensure_ascii=False)
            fp.write("\n")

# ---------------------------------------------------------------------------
# 交互式 CLI
# ---------------------------------------------------------------------------

def main() -> None:
    print("BADAPPLE")
    print("WEBUI 模式已启动，正在生成图片…")
    run_webui_program()
    print("首轮生成完成，请前往 ./image 文件夹查看。")

    while True:
        user_input = input("请输入需要重绘的图片编号（空格分隔，输入 N 退出）：").strip()
        if user_input.upper() == "N":
            break

        try:
            indices = [int(part) - 1 for part in user_input.split() if part.isdigit() and int(part) > 0]
        except ValueError:
            print("输入格式有误，请重新输入！")
            continue

        if not indices:
            print("未检测到有效编号，跳过。")
            continue

        # 删除旧图，为重绘做准备
        for n in indices:
            fname = f"output_{n + 1}.png"
            fpath = os.path.join(IMAGE_DIR, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
                print(f"已删除旧文件：{fname}")
            else:
                print(f"文件不存在，跳过：{fname}")

        print("开始重绘…")
        run_webui_program(prompts_to_redraw=indices)
        print("重绘完成！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，程序已退出。")
        sys.exit(0)
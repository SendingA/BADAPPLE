#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid
import io
import random
import urllib.request
import urllib.parse

import websocket  # pip install websocket-client
import openpyxl
import chardet
import logging
from tqdm import tqdm
from PIL import Image
from typing import Any, Optional

# 设置调试模式（修改 DEBUG 为 False 可关闭调试日志）
DEBUG: bool = False
if DEBUG:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 全局配置
SERVER_ADDRESS: str = "127.0.0.1:8188"  # ComfyUI 默认端口
CLIENT_ID: str = str(uuid.uuid4())
current_dir: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -------------------------------
# ComfyUI API 相关函数
# -------------------------------

def enqueue_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """
    将给定的 ComfyUI workflow 发送至 /prompt 接口，并返回服务器响应。
    """
    data = json.dumps({"prompt": workflow, "client_id": CLIENT_ID}).encode("utf-8")
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def fetch_image_data(filename: str, subfolder: str, folder_type: str) -> bytes:
    """
    通过 HTTP GET 请求从服务器获取图像二进制数据。
    """
    params = {
        "filename": filename,
        "subfolder": subfolder,
        "type": folder_type
    }
    url_params = urllib.parse.urlencode(params)
    url = f"http://{SERVER_ADDRESS}/view?{url_params}"
    with urllib.request.urlopen(url) as response:
        return response.read()

def collect_generated_images(ws: websocket.WebSocket, workflow: dict[str, Any]) -> dict[str, bytes]:
    """
    通过 WebSocket 执行 workflow，并监听返回消息，
    当检测到 SaveImage 节点执行完成后，通过 HTTP 获取生成的图像数据。
    在接收到 "progress" 消息时，不输出日志，而是更新进度条显示当前进度。
    """
    response = enqueue_workflow(workflow)
    prompt_id: str = response["prompt_id"]

    image_metadata = None
    pbar = None  # 用于显示进度条

    while True:
        raw_message = ws.recv()
        if isinstance(raw_message, str):
            message = json.loads(raw_message)
            msg_type = message.get("type")
            if msg_type == "progress":
                # 更新进度条显示
                value = message["data"].get("value", 0)
                max_val = message["data"].get("max", 100)
                if pbar is None:
                    pbar = tqdm(total=max_val, desc="Progress", leave=True)
                else:
                    diff = value - pbar.n
                    if diff > 0:
                        pbar.update(diff)
                continue  # 跳过后续处理，直接等待下一个消息
            else:
                if DEBUG:
                    logging.debug("WS Msg: %s", message)
            if msg_type == "executed" and message["data"].get("prompt_id") == prompt_id:
                # 检测 SaveImage 节点（可能返回 "SaveImage" 或 "9"）
                if message["data"].get("node") in ["SaveImage", "9"]:
                    image_metadata = message["data"]["output"].get("images")
            if msg_type == "executing" and message["data"].get("node") is None:
                break
        else:
            pass

    if pbar is not None:
        pbar.close()

    images: dict[str, bytes] = {}
    if image_metadata:
        for img_info in image_metadata:
            filename = img_info.get("filename", "")
            subfolder = img_info.get("subfolder", "")
            folder_type = img_info.get("type", "")
            img_bytes = fetch_image_data(filename, subfolder, folder_type)
            images[filename] = img_bytes
    return images

def build_workflow(
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    cfg: float,
    sampler_name: str,
    steps: int,
    model_name: str,
    clip_name1: str,
    clip_name2: str,
    clip_name3: str,
    seed: Optional[int] = None,
    seed_behavior: str = "randomize",
    scheduler: str = "normal",
    denoise: float = 1.0,
    batch_size: int = 1
) -> dict[str, Any]:
    """
    根据参数生成适用于 ComfyUI 的 workflow 字典。
    所有绘图相关参数均在此配置。
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    return {
        "3": {
            "inputs": {
                "seed": seed,
                "seed_behavior": seed_behavior,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            },
            "class_type": "KSampler",
            "_meta": {"title": "K采样器"}
        },
        "4": {
            "inputs": {"ckpt_name": model_name},
            "class_type": "CheckpointLoaderSimple",
            "_meta": {"title": "Checkpoint加载器（简易）"}
        },
        "5": {
            "inputs": {"width": width, "height": height, "batch_size": batch_size},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "空Latent图像"}
        },
        "6": {
            "inputs": {"text": positive_prompt, "clip": ["10", 0]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP文本编码"}
        },
        "7": {
            "inputs": {"text": negative_prompt, "clip": ["10", 0]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP文本编码"}
        },
        "8": {
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            "class_type": "VAEDecode",
            "_meta": {"title": "VAE解码"}
        },
        "9": {
            "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]},
            "class_type": "SaveImage",
            "_meta": {"title": "保存图像"}
        },
        "10": {
            "inputs": {"clip_name1": clip_name1, "clip_name2": clip_name2, "clip_name3": clip_name3},
            "class_type": "TripleCLIPLoader",
            "_meta": {"title": "三重CLIP加载器"}
        }
    }

# -------------------------------
# Excel 相关函数
# -------------------------------

def get_prompts(path: str) -> list[str]:
    """
    从 Excel 文件中读取提示语，取第 C 列中非空的单元格内容。
    """
    prompts_file = os.path.join(current_dir, path)
    wb = openpyxl.load_workbook(prompts_file)
    sheet = wb.active
    prompts = [cell.value for cell in sheet['C'] if cell.value]
    wb.close()
    return prompts

# -------------------------------
# 使用 ComfyUI API 绘图流程
# -------------------------------

def run_comfyui_program(prompts_to_redraw: Optional[list[int]] = None, extra_data: dict[str, Any] = {}) -> None:
    """
    使用 ComfyUI API 根据 Excel 中的提示语生成图像。
    若 prompts_to_redraw 为 None，则处理所有提示；否则仅处理指定下标的提示（下标从 0 开始）。
    extra_data 中可包含额外的 workflow 参数，会 merge 到 build_workflow 的参数中。
    """
    prompts = get_prompts(os.path.join('txt', 'txt2.xlsx'))
    image_dir = os.path.join(current_dir, 'image')
    os.makedirs(image_dir, exist_ok=True)

    # 枚举所有提示；若指定 prompts_to_redraw，则只处理对应索引的提示
    prompts_to_process = list(enumerate(prompts))
    if prompts_to_redraw is not None:
        prompts_to_process = [(i, p) for i, p in prompts_to_process if i in prompts_to_redraw]

    existing_files = set(os.listdir(image_dir))

    # 默认绘图参数
    default_params = {
        "width": 1024,
        "height": 1024,
        "cfg": 7.0,
        "sampler_name": "euler",
        "steps": 100,
        "model_name": "sd3.5_large.safetensors",
        "clip_name1": "clip_g.safetensors",
        "clip_name2": "clip_l.safetensors",
        "clip_name3": "t5xxl_fp16.safetensors",
        "seed": 916314980333822,
        "seed_behavior": "randomize",
        "scheduler": "normal",
        "denoise": 1.0,
        "batch_size": 1
    }
    default_params.update(extra_data)

    with open("../config.json", "r", encoding="utf-8") as f:
        config = json.load(f)



    for i, prompt_text in tqdm(prompts_to_process, desc='绘图进度', unit='image'):
        # 直接使用 Excel 中的提示作为正面提示，负面提示为空
        more_details = config.get("more_details")
        positive_prompt = f"{prompt_text},{more_details}"
        negative_prompt = config.get("negative_prompt")

        output_file = f'output_{i+1}.png'
        if output_file in existing_files and prompts_to_redraw is None:
            continue

        workflow = build_workflow(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=default_params["width"],
            height=default_params["height"],
            cfg=default_params["cfg"],
            sampler_name=default_params["sampler_name"],
            steps=default_params["steps"],
            model_name=default_params["model_name"],
            clip_name1=default_params["clip_name1"],
            clip_name2=default_params["clip_name2"],
            clip_name3=default_params["clip_name3"],
            seed=default_params["seed"],
            seed_behavior=default_params["seed_behavior"],
            scheduler=default_params["scheduler"],
            denoise=default_params["denoise"],
            batch_size=default_params["batch_size"]
        )

        # 使用 WebSocket 与 ComfyUI 通信
        ws = websocket.WebSocket()
        ws.connect(f"ws://{SERVER_ADDRESS}/ws?clientId={CLIENT_ID}")
        generated_images = collect_generated_images(ws, workflow)
        ws.close()

        if generated_images:
            for fname, img_data in generated_images.items():
                save_path = os.path.join(image_dir, output_file)
                with open(save_path, "wb") as f:
                    f.write(img_data)
                logging.info("Saved image to: %s", save_path)
            # 保存绘图参数
            temp_dir = os.path.join(current_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            with open(os.path.join(temp_dir, 'params.json'), 'a', encoding="utf-8") as f:
                json.dump({output_file: workflow}, f, ensure_ascii=False)
                f.write('\n')
        else:
            logging.error("未获取到图片：%s", output_file)

# -------------------------------
# 主程序流程
# -------------------------------

if __name__ == '__main__':
    print("BADAPPLE")

    # 固定使用本地 ComfyUI API 地址
    cloud_address = f"http://{SERVER_ADDRESS}"
    print("使用本地ComfyUI")

    print("ComfyUI 正在绘图，请稍后...")
    run_comfyui_program(extra_data={})
    print("绘图完成，请检查图片。")

    while True:
        user_input = input("请输入需要重绘的图片对应的数字（多个数字用空格隔开，输入N退出程序）: ")
        if user_input.upper() == "N":
            break

        file_numbers_to_redraw = []
        for s in user_input.split():
            try:
                idx = int(s.strip()) - 1
                file_name = f"output_{idx+1}.png"
                file_path = os.path.join(current_dir, 'image', file_name)
                if os.path.exists(file_path):
                    file_numbers_to_redraw.append(idx)
                    os.remove(file_path)
                    print(f"重绘图片: {file_name}")
                else:
                    print(f"无效图片: {file_name}")
            except ValueError:
                print(f"无效输入: {s.strip()}，跳过")

        if file_numbers_to_redraw:
            print("ComfyUI 正在重绘，请稍后...")
            run_comfyui_program(prompts_to_redraw=file_numbers_to_redraw, extra_data={})
            print("重绘完成，请检查图片。")
        else:
            print("没有需要重绘的图片。")

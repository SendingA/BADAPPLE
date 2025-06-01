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
import concurrent.futures
import threading
from queue import Queue

import openpyxl  # pip install openpyxl
import requests  # pip install requests
from tqdm import tqdm  # pip install tqdm

import glob
from PIL import Image

# ---------------------------------------------------------------------------
# 日志与全局常量
# ---------------------------------------------------------------------------
DEBUG: bool = False  # 修改为 True 可开启调试输出
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# WebUI 服务器地址列表，支持多个服务器
DEFAULT_SERVERS = [
    f"http://172.18.36.54:{port}" for port in range(7860, 7870)
]
SERVER_URLS: list[str] = []

def set_server_urls(urls: list[str]) -> None:
    """设置WebUI服务器地址列表"""
    global SERVER_URLS
    SERVER_URLS = [url.rstrip("/") for url in urls if url.strip()]
    if not SERVER_URLS:
        SERVER_URLS = DEFAULT_SERVERS

# 初始化默认服务器
env_urls = os.getenv("WEBUI_SERVER_URLS", "")
if env_urls:
    set_server_urls(env_urls.split(","))
else:
    set_server_urls(DEFAULT_SERVERS)

CURRENT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_XLSX: str = os.path.join(CURRENT_DIR, "txt", "output.xlsx")
IMAGE_DIR: str = os.path.join(CURRENT_DIR, "image")
PARAMS_LOG: str = os.path.join(CURRENT_DIR, "temp", "params.jsonl")
print(CURRENT_DIR)
# 创建必要目录
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PARAMS_LOG), exist_ok=True)

# 线程安全的日志写入锁
log_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Excel 工具函数
# ---------------------------------------------------------------------------
def count_character(prompts: list[str]) ->list[int]:
    """统计每个提示词中字符的数量，返回一个整数列表。"""
    return [prompt.count('BREAK') for prompt in prompts]


def get_prompts(path: str) -> list[str]:
    """读取指定 Excel 文件第 C 列中的非空单元格，返回提示词列表。"""

    wb = openpyxl.load_workbook(path)
    sheet = wb.active
    prompts = [cell.value for cell in sheet["C"] if cell.value]
    wb.close()
    return prompts

# ---------------------------------------------------------------------------
# WebUI 相关辅助函数
# ---------------------------------------------------------------------------

def _encode_image_to_base64(path: str) -> str:
    """将本地图片文件编码为 base64 字符串。"""

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def txt2img(payload: dict[str, Any], server_url: str) -> bytes:
    """调用指定WebUI服务器的txt2img接口并返回第一张图片的二进制数据。"""
    txt2img_url = f"{server_url}/sdapi/v1/txt2img"
    resp = requests.post(txt2img_url, json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("images"):
        raise RuntimeError(f"WebUI服务器 {server_url} 未返回任何图像！")
    return base64.b64decode(data["images"][0])

def get_server_status(server_url: str) -> bool:
    """检查WebUI服务器状态"""
    try:
        resp = requests.get(f"{server_url}/sdapi/v1/memory", timeout=5)
        return resp.status_code == 200
    except:
        return False

def get_available_servers() -> list[str]:
    """获取可用的WebUI服务器列表"""
    available = []
    for server in SERVER_URLS:
        if get_server_status(server):
            available.append(server)
            logging.info(f"服务器可用: {server}")
        else:
            logging.warning(f"服务器不可用: {server}")
    return available

# ---------------------------------------------------------------------------
# 单个图片生成任务
# ---------------------------------------------------------------------------

def generate_single_image(task_info: dict) -> tuple[int, bool, str]:
    """生成单张图片的任务函数
    
    Args:
        task_info: 包含生成参数的字典
        
    Returns:
        tuple: (索引, 是否成功, 错误信息)
    """
    idx = task_info["idx"]
    prompt_core = task_info["prompt"]
    regional_counts = task_info["regional_counts"]
    params = task_info["params"]
    negative_prompt = task_info["negative_prompt"]
    encoded_control_img = task_info["encoded_control_img"]
    server_url = task_info["server_url"]
    
    try:
        # 构建区域分割参数
        regional_division = "1"
        if regional_counts > 1:
            regional_division += ",1" * (regional_counts - 1)
        
        positive_prompt = f"{prompt_core}"

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
                    "Regional Prompter": {
                        "args": [
                            True,                  # 1  Active
                            False,                 # 2  debug
                            "Matrix",              # 3  Mode
                            "Vertical",            # 4  Mode (Matrix)
                            "Mask",                # 5  Mode (Mask)
                            "Prompt",              # 6  Mode (Prompt)
                            regional_division,               # 7  Ratios
                            "",                    # 8  Base Ratios
                            False,                 # 9  Use Base
                            False,                 # 10 Use Common
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
                    }
                }
            )

        # 生成图片
        img_bytes = txt2img(payload, server_url)
        
        # 保存图片
        out_name = f"output_{idx + 1}.png"
        out_path = os.path.join(IMAGE_DIR, out_name)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        
        # 线程安全地记录参数
        with log_lock:
            with open(PARAMS_LOG, "a", encoding="utf-8") as fp:
                json.dump({out_name: payload}, fp, ensure_ascii=False)
                fp.write("\n")
        
        logging.info(f"图片已保存 → {out_path} (服务器: {server_url})")
        return idx, True, ""
        
    except Exception as exc:
        error_msg = f"生成失败（#%d）：%s (服务器: %s)" % (idx + 1, exc, server_url)
        logging.error(error_msg)
        return idx, False, str(exc)

# ---------------------------------------------------------------------------
# 核心生成流程（并行版本）
# ---------------------------------------------------------------------------

def run_webui_program(
    prompts_to_redraw: Optional[list[int]] = None,
    extra_params: dict[str, Any] | None = None,
    control_image: str | None = None,
    max_workers: int = None,
) -> None:
    """批量生成（或重绘）PNG 图片，支持多服务器并行。"""

    # 获取可用服务器
    available_servers = get_available_servers()
    if not available_servers:
        raise RuntimeError("没有可用的WebUI服务器！请检查服务器状态。")
    
    logging.info(f"使用 {len(available_servers)} 个可用服务器: {available_servers}")
    
    # 设置最大并行数
    if max_workers is None:
        max_workers = len(available_servers)
    max_workers = min(max_workers, len(available_servers))
    
    prompts = get_prompts(PROMPT_XLSX)
    break_counts = count_character(prompts)

    # 需要处理的索引集合
    indices = (
        prompts_to_redraw
        if prompts_to_redraw is not None
        else list(range(len(prompts)))
    )

    # 默认生成参数，可根据需要修改
    params: dict[str, Any] = {
        "width": 512,
        "height": 512,
        "steps": 50,
        "sampler_name": "DPM++ 3M SDE",
        "scheduler": "Karras",
        "batch_size": 1,
        "cfg_scale": 7,
        "seed": -1,  # -1 代表 WebUI 随机种子
        "enable_hr": True,
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
    more_details: str = user_cfg.get("more_details", "")
    negative_prompt: str = user_cfg.get("negative_prompt", "")

    # 控制图（如果提供）
    encoded_control_img = _encode_image_to_base64(control_image) if control_image else None

    # 准备任务列表
    tasks = []
    for i, idx in enumerate(indices):
        prompt_core = prompts[idx]
        regional_counts = break_counts[idx]
        
        # 轮询分配服务器
        server_url = available_servers[i % len(available_servers)]
        
        task_info = {
            "idx": idx,
            "prompt": prompt_core,
            "regional_counts": regional_counts,
            "params": params,
            "negative_prompt": negative_prompt,
            "encoded_control_img": encoded_control_img,
            "server_url": server_url
        }
        tasks.append(task_info)

    # 并行执行任务
    success_count = 0
    failed_indices = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_task = {executor.submit(generate_single_image, task): task for task in tasks}
        
        # 使用 tqdm 显示进度
        with tqdm(total=len(tasks), desc="并行生成中", unit="张") as pbar:
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    idx, success, error_msg = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_indices.append(idx + 1)
                except Exception as exc:
                    failed_indices.append(task["idx"] + 1)
                    logging.error(f"任务执行异常: {exc}")
                
                pbar.update(1)
    
    # 输出统计信息
    logging.info(f"生成完成！成功: {success_count}/{len(tasks)}")
    if failed_indices:
        logging.warning(f"失败的图片索引: {failed_indices}")

def get_generated_images():
    """获取已生成的图片信息，按场景分组"""
    # 读取场景分割信息
    scenarios_file = os.path.join(CURRENT_DIR, "scripts", "场景分割.json")
    if not os.path.exists(scenarios_file):
        return []
    
    with open(scenarios_file, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    
    # 获取所有生成的图片
    image_files = glob.glob(os.path.join(IMAGE_DIR, "output_*.png"))
    image_files.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
    
    # 按场景分组
    grouped_images = []
    for scenario_key, scenario_data in scenarios.items():
        if '子图索引' in scenario_data:
            scene_images = []
            for sub_idx in scenario_data['子图索引']:
                img_path = os.path.join(IMAGE_DIR, f"output_{sub_idx + 1}.png")
                if os.path.exists(img_path):
                    scene_images.append({
                        'path': img_path,
                        'index': sub_idx + 1,
                        'name': f"output_{sub_idx + 1}.png"
                    })
            
            if scene_images:
                grouped_images.append({
                    'scenario': scenario_key,
                    'content': scenario_data.get('内容', ''),
                    'images': scene_images
                })
    
    return grouped_images

def regenerate_images(indices):
    """重新生成指定索引的图片"""
    if not indices:
        return "请选择要重绘的图片"
    
    try:
        # 将1基索引转换为0基索引
        zero_based_indices = [i - 1 for i in indices]
        
        # 删除旧图片
        for idx in zero_based_indices:
            old_path = os.path.join(IMAGE_DIR, f"output_{idx + 1}.png")
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # 重新生成
        run_webui_program(prompts_to_redraw=zero_based_indices)
        return f"成功重绘了 {len(indices)} 张图片"
        
    except Exception as e:
        return f"重绘失败: {str(e)}"

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

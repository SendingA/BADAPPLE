import json
import uuid
import io
import random
import urllib.request
import urllib.parse
import websocket  # pip install websocket-client
from PIL import Image
from typing import Any, Optional
import logging

# 设置调试模式（修改 DEBUG 为 False 可关闭调试日志）
DEBUG: bool = True

if DEBUG:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 全局配置（请根据实际情况修改）
SERVER_ADDRESS: str = "127.0.0.1:8188"
CLIENT_ID: str = str(uuid.uuid4())

def enqueue_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """
    将给定的 ComfyUI workflow 发送至 /prompt 接口，并返回服务器响应。

    :param workflow: ComfyUI workflow 字典
    :return: 服务器返回的 JSON 数据（通常包含 prompt_id）
    """
    data = json.dumps({"prompt": workflow, "client_id": CLIENT_ID}).encode("utf-8")
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def fetch_image_data(filename: str, subfolder: str, folder_type: str) -> bytes:
    """
    通过 HTTP GET 请求从服务器获取图像二进制数据。

    :param filename: 服务器保存的文件名
    :param subfolder: 图像所在的子文件夹
    :param folder_type: 文件类型（例如 "output"）
    :return: 图像的二进制数据
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

def fetch_execution_history(prompt_id: str) -> dict[str, Any]:
    """
    获取指定 prompt_id 的执行历史记录。

    :param prompt_id: ComfyUI 分配的提示 ID
    :return: 执行历史的 JSON 数据
    """
    url = f"http://{SERVER_ADDRESS}/history/{prompt_id}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def collect_generated_images(ws: websocket.WebSocket, workflow: dict[str, Any]) -> dict[str, bytes]:
    """
    通过 WebSocket 执行 workflow，并监听返回消息，
    当检测到 SaveImage 节点执行完成后，通过 HTTP 获取生成的图像数据。

    :param ws: 已连接的 WebSocket 对象
    :param workflow: ComfyUI workflow 字典
    :return: {filename: image_bytes} 的字典
    """
    response = enqueue_workflow(workflow)
    prompt_id: str = response["prompt_id"]

    image_metadata = None

    while True:
        raw_message = ws.recv()
        if isinstance(raw_message, str):
            message = json.loads(raw_message)
            if DEBUG:
                logging.debug("Msg: %s", message)

            if message.get("type") == "executed" and message["data"].get("prompt_id") == prompt_id:
                # 判断节点标识，可以根据返回的节点号或名称来匹配
                if message["data"].get("node") in ["SaveImage", "9"]:
                    image_metadata = message["data"]["output"].get("images")

            # 当检测到执行结束（node 为 None）时退出循环
            if message.get("type") == "executing" and message["data"].get("node") is None:
                break
        else:
            # 如果服务器发送二进制消息（目前不适用），可在此处理
            pass

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

    :param positive_prompt: 正面提示词
    :param negative_prompt: 负面提示词
    :param width: 图像宽度
    :param height: 图像高度
    :param cfg: CFG scale
    :param sampler_name: 采样器名称（例如 "euler"）
    :param steps: 采样步数
    :param model_name: 检查点文件名 (ckpt_name)
    :param clip_name1: 第一个 CLIP 模型名称
    :param clip_name2: 第二个 CLIP 模型名称
    :param clip_name3: 第三个 CLIP 模型名称
    :param seed: 随机种子；若为 None，则自动生成
    :param seed_behavior: 生成后控制 ("randomize" / "keep" / "iter" 等)
    :param scheduler: 调度器 ("normal", "ddim", "karras" 等)
    :param denoise: 降噪强度
    :param batch_size: 生成图像的批量大小
    :return: ComfyUI workflow 字典
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    return {
        "3": {
            "inputs": {
                "seed": seed,
                "seed_behavior": seed_behavior,   # 生成后控制
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,           # 调度器
                "denoise": denoise,               # 降噪
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

def execute_comfyui_pipeline(
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    cfg: float,
    sampler_name: str,
    steps: int,
    model_name: str = "sd3.5_large.safetensors",
    clip_name1: str = "clip_g.safetensors",
    clip_name2: str = "clip_l.safetensors",
    clip_name3: str = "t5xxl_fp16.safetensors",
    seed: Optional[int] = None,
    seed_behavior: str = "randomize",
    scheduler: str = "normal",
    denoise: float = 1.0,
    batch_size: int = 1
) -> None:
    """
    执行 ComfyUI workflow 流程，根据传入参数生成图像，并以 PNG 格式保存。

    :param positive_prompt: 正面提示词
    :param negative_prompt: 负面提示词
    :param width: 图像宽度
    :param height: 图像高度
    :param cfg: CFG scale
    :param sampler_name: 采样器名称
    :param steps: 采样步数
    :param model_name: 模型名称（检查点）
    :param clip_name1: 第一个 CLIP 模型名称
    :param clip_name2: 第二个 CLIP 模型名称
    :param clip_name3: 第三个 CLIP 模型名称
    :param seed: 随机种子；若为 None，则自动生成
    :param seed_behavior: 生成后控制选项 ("randomize"/"keep"/"iter"等)
    :param scheduler: 调度器 ("normal", "karras", "ddim"等)
    :param denoise: 降噪强度
    :param batch_size: 批量生成数量
    """
    workflow: dict[str, Any] = build_workflow(
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        cfg=cfg,
        sampler_name=sampler_name,
        steps=steps,
        model_name=model_name,
        clip_name1=clip_name1,
        clip_name2=clip_name2,
        clip_name3=clip_name3,
        seed=seed,
        seed_behavior=seed_behavior,
        scheduler=scheduler,
        denoise=denoise,
        batch_size=batch_size
    )
    ws = websocket.WebSocket()
    ws.connect(f"ws://{SERVER_ADDRESS}/ws?clientId={CLIENT_ID}")
    generated_images: dict[str, bytes] = collect_generated_images(ws, workflow)
    ws.close()
    for filename, image_data in generated_images.items():
        image = Image.open(io.BytesIO(image_data))
        image.save(filename, "PNG")
        print(f"Saved image to: {filename}")

if __name__ == "__main__":
    execute_comfyui_pipeline(
        positive_prompt=(
            """
            Japan Anime: In a lush forest with a carpet of fallen leaves and wild undergrowth, Dragon Haochen, focused and agile, is dressed in simple clothes and skillfully gathers wild vegetables. He carefully collects the vegetables and places them into a small bag. The mood is quiet, determined, and responsible, with natural greens and browns. Soft, diffused sunlight filters through the trees, creating a peaceful and grounded ambiance.
            """
        ),
        negative_prompt=(
            """
            text, error, cropped, worst quality, low quality, normal quality, signature, watermark, username, blurry, artist name, monochrome, sketch, censorship, censor, extra legs, extra hands, (forehead mark) (depth of field) (emotionless) (penis)
            """
        ),
        width=1024,
        height=1024,
        cfg=7.0,
        sampler_name="euler",
        steps=50,
        model_name="sd3.5_large.safetensors",
        clip_name1="clip_g.safetensors",
        clip_name2="clip_l.safetensors",
        clip_name3="t5xxl_fp16.safetensors",
        seed=916314980336220,
        seed_behavior="randomize",
        scheduler="normal",
        denoise=1.0,
        batch_size=1
    )

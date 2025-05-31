import requests
import base64

# 设置 API URL 和请求数据
url = "http://172.18.36.54:7862/sdapi/v1/txt2img"

# Read Image in RGB order

# Encode into PNG and send to ControlNet
with open("output.png", "rb") as f:
    bytes = f.read()
encoded_image = base64.b64encode(bytes).decode('utf-8')

payload = {
    "prompt": 'a beautiful queen',
    "negative_prompt": "",
    "sampler_name": "DPM++ 3M SDE",
    "scheduler": "Karras",
    "batch_size": 1,
    "steps": 50,
    "cfg_scale": 7,
    "enable_hr": True,
    "hr_scale": 2,
    "hr_upscaler": "Latent",
    "denoising_strength": 0.7,
    "alwayson_scripts": {
        "controlnet": {
            "args": [
                {
                    "enabled": True,
                    "image": encoded_image,
                    "module": "ip-adapter-auto",
                    "model": "ip-adapter_sd15_plus [32cd8f7f]",

                },
                # {
                #     "enabled": True,
                #     "image": encoded_image,
                #     "module": "instant_id_face_embedding",
                #     "model": "instant_id_sd15 [61a0b394]",

                # },
            ]
        }
    }
}


# 发送 POST 请求
response = requests.post(url, json=payload)
response.raise_for_status()  # 检查请求是否成功


# 解析响应并保存图像
data = response.json()
image_data = base64.b64decode(data['images'][0])
with open("output.png", "wb") as f:
    f.write(image_data)
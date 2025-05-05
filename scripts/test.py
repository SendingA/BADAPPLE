import base64
from openai import OpenAI

client = OpenAI(
api_key="sk-cLHG0jRuBeFDE49617b9T3BLBkFJe5b79d2bDefD4Db7b9fa",
base_url="https://cn2us02.opapi.win/v1",
)

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Path to your image
image_path = "C:\\Users\\William\\MIP_Project\\BADAPPLE\\scripts\\1.png"

# Getting the Base64 string
base64_image = encode_image(image_path)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}"  # 注意如果是PNG别写JPEG
                }
            }
        ]
    }
]


response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=messages
)

print(response.choices[0].message.content)
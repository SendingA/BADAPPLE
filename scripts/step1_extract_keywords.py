import os
import openpyxl
import spacy
from openai import AsyncOpenAI
import time
import json
import chardet
import asyncio
from docx import Document
from tqdm import tqdm
import pandas as pd
from tqdm.asyncio import tqdm_asyncio

openai = AsyncOpenAI(
    api_key="sk-883af3c325b140c3986f45704410f614",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# openai = AsyncOpenAI(
#     api_key="sk-cLHG0jRuBeFDE49617b9T3BLBkFJe5b79d2bDefD4Db7b9fa",
#     base_url="https://c-z0-api-01.hash070.com/v1",
# )

nlp = spacy.load("zh_core_web_sm")

default_trigger = """Task: I will give you the theme in natural language. Your task is to imagine a full picture based on that theme and convert it into a high-quality prompt for Stable Diffusion.  

Prompt concept: A prompt describes the content of an image using simple, commonly used English tags separated by English half-width commas (','). Each word or phrase is a tag.  

Prompt requirements: 
The prompt should include the following elements:
- Main subject (e.g. a girl in a garden), enriched with relevant details depending on the theme.
- For characters, describe facial features like 'beautiful detailed eyes, beautiful detailed lips, extremely detailed eyes and face, long eyelashes' to prevent facial deformities.
- Additional scene or subject-related details.
- Image quality tags such as '(best quality,4k,8k,highres,masterpiece:1.2), ultra-detailed, (realistic,photorealistic,photo-realistic:1.37)' and optionally: HDR, UHD, studio lighting, ultra-fine painting, sharp focus, extreme detail description, professional, vivid colors, bokeh, physically-based rendering.
- Artistic style, color tone, and lighting should also be included in tags.

The prompt format:
{Character overview and count, e.g. one boy, one girl and a man}  
{Full scene description including environment, mood, lighting, style, and image quality tags}  
BREAK  
{Prompt for the first character}  
BREAK  
{Prompt for the second character}  
BREAK  
{Prompt for the third character}

.......

One prompt example for 2 characters:
one middle aged king and one queen about thirty,starry sky background, flickering candlelights, garden setting, eyes closed, offering silent prayers, dynamic composition, HDR, UHD, sharp details, professional, bokeh, physically based rendering, ultra detailed, aesthetic
BREAK
middle aged king with a dignified appearance, splendid golden robe, gem encrusted crown, detailed facial features, beautiful detailed eyes, long eyelashes, realistic skin tones, sharp focus, ultra fine painting, (masterpiece:1.2), (best quality,4k,8k,highres:1.3),
BREAK
(queen, first wife, woman in her thirties), fair skin, slender figure, long black hair, silk gown with intricate embroidery, pearl hair ornament, gentle maternal eyes, elegant posture, (realistic,photorealistic:1.37), vivid colors, studio lighting, perfect lighting


Attention!
If there is no character in the scene, DON'T USE BREAK, you can use the following format to generate a scene without characters:
{Scene description, e.g. a beautiful garden with flowers and trees, a starry sky, a flickering candlelight, a garden setting, a dynamic composition, HDR, UHD, sharp details, professional, bokeh, physically based rendering, ultra detailed, aesthetic}

The text content is as follows:
"""


def load_config():
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file = os.path.join(current_dir, "config.json")

    with open(config_file, "rb") as f:
        encoding = chardet.detect(f.read())["encoding"]

    with open(config_file, "r", encoding=encoding) as f:
        return json.load(f)

async def replace_character(scenarios, character_dict):
    system_prompt = (
        "你将收到一段文本，以及一个包含角色名称与其特征的映射字典。"
        "请识别文本中所有出现的角色名称，以及指代这些角色的代词、描述性名词、外貌称呼或亲属关系描述。"
        "请统一将这些指代或称呼替换为字典中定义的标准角色名称，保持上下文一致，避免遗漏或误替换，并与原文的格式保持一致，在替代的时候不要出现无关的符号。"
        "如果同一角色在不同阶段（如童年、成年）被赋予不同称呼，请根据上下文推理，并统一替换为同一个角色名。"
        "对于包含亲属关系的表达（如“某某的母亲”、“她的父亲”），请结合上下文，明确识别‘某某’指的是谁，"
        "再在字典中查找其母亲（或父亲）是谁，并替换为该角色的标准名称。"
        "例如，如果“白雪公主（儿童）”和“王后（白雪公主生母）”都出现在字典中，且提到“白雪公主（美少女）的母亲”，"
        "应识别出“白雪公主（美少女）”与“白雪公主（儿童）”为同一人，其母亲即“王后（白雪公主生母）”，应替换为后者。"
        "保持文本原有格式和结构，不要添加、修改或省略任何内容，也不要输出 prompt 以外的任何信息。"
    )

    scenario_text = "\n".join(scenarios["Chinese Content"].tolist())

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f'角色名称与其特征的映射字典如下：{character_dict}\n\n文本如下：{scenario_text}'
        },
    ]

    resp = await request_with_retry_async(messages)
    return [row.strip() for row in resp.split("\n") if row.strip()]


def replace_keywords(sentence, keyword_dict):
    for key, value in keyword_dict.items():
        if key and value:
            sentence = sentence.replace(key, f'{key}(character features: {value})')
    return sentence

async def json_request_with_retry_async(
    messages, max_requests=90, cooldown_seconds=60
):
    """异步版本的API请求函数"""
    import re
    import json
    attempts = 0
    while attempts < max_requests:
        try:
            response = await openai.chat.completions.create(
                model="qwen-plus",
                # model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"},
            )
            result = response.choices[0].message.content
            cleaned = re.sub(r'^```json|```$', '', result.strip(), flags=re.MULTILINE).strip()
            json_data = json.loads(cleaned)
            return json_data
        except Exception as e:
            print(f"发生错误：{str(e)}")
            await asyncio.sleep(10)
        attempts += 1

    return "请求失败，已达到最大尝试次数"


async def request_with_retry_async(
    messages, max_requests=90, cooldown_seconds=60
):
    """异步版本的API请求函数"""
    attempts = 0
    while attempts < max_requests:
        try:
            response = await openai.chat.completions.create(
                model="qwen-plus",
                # model="gpt-4o-mini",
                messages=messages,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"发生错误：{str(e)}")
            await asyncio.sleep(10)
        attempts += 1

    return "请求失败，已达到最大尝试次数"


async def translate_to_english_async(text):
    """异步版本的英文翻译函数"""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": f'Translate the following text into English: "{text}". Do not directly translate, but instead translate from a third-person descriptive perspective, and complete the missing subject, predicate, object, attributive, adverbial, and complement in the text. Besides the translated result, do not include any irrelevant content or explanations in your response.',
        },
    ]
    return await request_with_retry_async(messages)


async def translate_to_storyboard_async(text, trigger):
    """异步版本的分镜生成函数"""
    messages = [
        {
            "role": "system",
            "content": "StableDiffusion is a deep learning text-to-image model that supports the generation of new images using keywords to describe the elements to be included or omitted. Now, as a professional StableDiffusion AI drawing keyword generator. You can assist me in generating keywords for my desired image.",
        },
        {"role": "user", "content": f"{trigger}'{text}'"},
    ]
    return await request_with_retry_async(messages)

def divide_image_async(text):
    """异步版本的图像分割函数"""
    prompt = f"""
    请将下面的一个场景描述，分割成若干个画面，你的目标是将该场景通过若干静态画面来展现，去除掉其中的人物对话部分。注意严格遵循原场景的文字描述去生成画面，不要添加任何额外信息。

    请返回JSON格式响应，键值对为"画面[NUMBER]": "[Scene Description]"
    场景描述如下：{text}
    """
    messages = [
        {"role": "system", "content": "你是一个专业的小说改编影视的编剧。"},
        {"role": "user", "content": prompt},
    ]
    return json_request_with_retry_async(messages)





# 假设这些函数已经定义好
# from your_module import translate_to_english_async, translate_to_storyboard_async, replace_keywords

async def process_text_sentences_async(
    input_file_path,
    output_file_path,
    trigger,
    keyword_dict,
):
    """
    异步处理 CSV 中的文本数据，包含关键词替换、翻译、StableDiffusion关键词生成。
    """

    # 读取 json 文件
    with open(input_file_path, "r", encoding="utf-8") as f:
        scenarios_json = json.load(f)
    scenarios_list = list(scenarios_json.values())
    scenario_keys = list(scenarios_json.keys())
    scenario_contents = [scenario['内容'] for scenario in scenarios_list]
    dataframe = pd.DataFrame(columns=["Chinese Content", "Replaced Content", "Translated Content", "SD Content"])
    print("🔍 正在划分子图...")
    subimg_tasks = [
        divide_image_async(text) for text in scenario_contents
    ]
    image_jsons = await tqdm_asyncio.gather(*subimg_tasks, desc="划分子图", ncols=80)
    # print(image_jsons)
    subimages = []
    start_idx = 0
    
    for i, image_json in enumerate(image_jsons):
        # 同时更新原始的scenarios_json
        scenarios_json[scenario_keys[i]]['子图索引'] = list(range(start_idx, start_idx + len(image_json)))
        start_idx += len(image_json)
        for image in image_json.values():
            # english_content = translate(image)
            subimages.append(image)
    dataframe['Chinese Content'] = subimages
    dataframe['Replaced Content'] = dataframe['Chinese Content'].copy()


    # 检查必须列
    if 'Replaced Content' not in dataframe.columns:
        raise ValueError("CSV中缺少'Replaced Content'这一列。")

    # 替换关键词（支持传入自定义的 replace_keywords 函数）
    dataframe['Replaced Content'] = dataframe['Replaced Content'].apply(replace_keywords, args=(keyword_dict,))

    # 异步翻译
    print("🔤 开始翻译内容...")
    translation_tasks = [
        translate_to_english_async(text) for text in dataframe['Replaced Content']
    ]
    dataframe['Translated Content'] = await tqdm_asyncio.gather(*translation_tasks, desc="翻译中", ncols=80)

    # 异步生成分镜脚本
    print("🎨 开始生成分镜脚本...")
    storyboard_tasks = [
        translate_to_storyboard_async(text, trigger) for text in dataframe['Translated Content']
    ]
    dataframe['SD Content'] = await tqdm_asyncio.gather(*storyboard_tasks, desc="生成分镜", ncols=80)

    # 保存结果
    with open(input_file_path, "w", encoding="utf-8") as f:
        json.dump(scenarios_json, f, indent=2, ensure_ascii=False)
    dataframe.to_csv(output_file_path, index=False)
    dataframe.to_excel(output_file_path.replace(".csv", ".xlsx"), index=False)
    print(f"✅ 已保存到 {output_file_path}")


async def regenerate_selected_storyboards(selected_indices, trigger):
    """重新生成指定索引的分镜脚本"""
    # 读取现有数据
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_file_path = os.path.join(current_dir, "txt", "output.csv")
    
    if not os.path.exists(output_file_path):
        return "❌ 未找到现有数据文件，请先执行完整的 Step 1"
    
    df = pd.read_csv(output_file_path)
    
    if not selected_indices:
        return "❌ 请选择要重新生成的分镜"
    
    # 验证索引
    valid_indices = [i for i in selected_indices if 0 <= i < len(df)]
    if not valid_indices:
        return "❌ 选择的索引无效"
    
    print(f"🎨 正在重新生成 {len(valid_indices)} 个分镜脚本...")
    
    # 重新生成选中的分镜脚本
    storyboard_tasks = [
        translate_to_storyboard_async(df.iloc[i]['Translated Content'], trigger) 
        for i in valid_indices
    ]
    
    new_storyboards = await tqdm_asyncio.gather(*storyboard_tasks, desc="重新生成分镜", ncols=80)
    
    # 更新数据
    for idx, new_storyboard in zip(valid_indices, new_storyboards):
        df.loc[idx, 'SD Content'] = new_storyboard
    
    # 保存更新后的数据
    df.to_csv(output_file_path, index=False)
    df.to_excel(output_file_path.replace(".csv", ".xlsx"), index=False)
    
    return f"✅ 已重新生成 {len(valid_indices)} 个分镜脚本并保存"

def get_current_storyboards():
    """获取当前的分镜脚本数据"""
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_file_path = os.path.join(current_dir, "txt", "output.csv")
    
    if not os.path.exists(output_file_path):
        return pd.DataFrame()
    
    df = pd.read_csv(output_file_path)
    # 添加索引列以便用户选择
    df.insert(0, '序号', range(len(df)))
    return df[['序号', 'Chinese Content', 'Translated Content', 'SD Content']]

async def main_async():
    """异步版本的主函数"""
    config = load_config()
    print("BADAPPLE")

    role_name = config.get("角色名1", "未指定角色名")
    feature = config.get("特征1", "未指定特征")
    role2_name = config.get("角色名2", "未指定角色名2")
    feature2 = config.get("特征2", "未指定特征2")
    role3_name = config.get("角色名3", "未指定角色名3")
    feature3 = config.get("特征3", "未指定特征3")
    role4_name = config.get("角色名4", "未指定角色名4")
    feature4 = config.get("特征4", "未指定特征4")
    role5_name = config.get("角色名5", "未指定角色名5")
    feature5 = config.get("特征5", "未指定特征5")
    role6_name = config.get("角色名6", "未指定角色名6")
    feature6 = config.get("特征6", "未指定特征6")
    role7_name = config.get("角色名7", "未指定角色名7")
    feature7 = config.get("特征7", "未指定特征7")
    role8_name = config.get("角色名8", "未指定角色名8")
    feature8 = config.get("特征8", "未指定特征8")
    role9_name = config.get("角色名9", "未指定角色名9")
    feature9 = config.get("特征9", "未指定特征9")
    role10_name = config.get("角色名10", "未指定角色名10")
    feature10 = config.get("特征10", "未指定特征10")
    keyword_dict = {
        role_name: feature,
        role2_name: feature2,
        role3_name: feature3,
        role4_name: feature4,
        role5_name: feature5,
        role6_name: feature6,
        role7_name: feature7,
        role8_name: feature8,
        role9_name: feature9,
        role10_name: feature10,
    }


    # trigger = config.get("引导词", default_trigger)
    trigger = default_trigger
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file_path = os.path.join(current_dir, "scripts", "场景分割.json")
    output_dir = os.path.join(current_dir, "txt")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    output_file_path = os.path.join(output_dir, "output.csv")

    await process_text_sentences_async(
        input_file_path,
        output_file_path,
        trigger,
        keyword_dict,
    )


def main():
    """入口函数，运行异步主函数"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
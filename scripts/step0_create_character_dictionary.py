import asyncio
from openai import AsyncOpenAI
import re
import os
import json
import pandas as pd
import aiofiles
from tqdm.asyncio import tqdm


client = AsyncOpenAI(
    api_key="sk-883af3c325b140c3986f45704410f614",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

async def update_config_with_characters(character_data, config_path="../config.json"):
    # 加载已有 config.json
    async with aiofiles.open(config_path, "r", encoding="utf-8") as f:
        content = await f.read()
        config = json.loads(content)

    # 清空原有的角色字段（角色名1~10 和 特征1~10）
    for i in range(1, 11):
        config[f"角色名{i}"] = ""
        config[f"特征{i}"] = ""

    # 写入新的角色信息
    for idx, (role_key, feature_value) in enumerate(character_data.items()):
        if "角色名" in role_key:
            role_index = idx // 2 + 1
            config[f"角色名{role_index}"] = feature_value
        elif "特征" in role_key:
            feature_index = idx // 2 + 1
            config[f"特征{feature_index}"] = feature_value

    # 保存回 config.json
    async with aiofiles.open(config_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(config, indent=2, ensure_ascii=False))
    print("✅ config.json 已成功更新。")


async def extract_character_features(text):
    system_prompt = '''请阅读以下中文小说文本，并识别所有明确提到的"角色名"及其"特征描述"，并将结果用 JSON 结构返回。
    JSON的键值对为"角色名": "xxx", "特征": "xxx"
    提取规范：
    1.仅提取小说中真实出现的角色名称，不可虚构角色，请提取出所有的角色。

    2.每个角色如果在文本中经历明显成长（如婴儿、少女、成年）或变化为了不同的形态和样貌，请为每个阶段分别提取特征，名称中用括号注明阶段，如："帕奇（儿童）"、"帕奇（成年）"、帕奇（整容后）。

    3.特征描述必须足够的具象和立体，不要出现"漂亮"，"慈祥"，"华丽"等抽象的描述，请务必包括以下信息：

    年龄段（如"十五六岁"、"约三十岁"）

    外貌（发色、发型、肤色、眼睛、身材、神态）

    衣着（服装颜色、材质、图案、饰品、鞋子等）

    4.编造补全说明：如文本未提及角色的某项外貌/服饰特征，可结合上下文风格合情合理地补全细节，避免留空，并不要出现"可能为"的字样。

    5.禁止输出人物关系、性格或心理活动（如"善良""脾气暴躁"等）。
    例子：
      {"角色名1": "帕奇（成年）",
      "特征1": "一位身材高大的中年男子，蓄着整齐的深棕色胡须，面容威严却略带疲态，头戴镶嵌红宝石的金色王冠，身穿红黑相间的长袍，肩披白底黑点的毛皮披风，腰间悬挂金色佩剑，行走时脚步沉稳有力",

      "角色名2": "",
      "特征2": "",

      "角色名3": "",
      "特征3": ""}
    '''

    prompt = f"""小说内容如下：{text}"""

    response = await client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.5
    )

    result = response.choices[0].message.content

    try:
        cleaned = re.sub(r'^```json|```$', '', result.strip(), flags=re.MULTILINE).strip()
        json_data = json.loads(cleaned)
        async with aiofiles.open("角色信息.json", "w", encoding="utf-8") as f:
            await f.write(json.dumps(json_data, indent=2, ensure_ascii=False))
        return json_data
    except json.JSONDecodeError:
        print("返回内容不是合法的 JSON，可以考虑用正则或人工检查")
        return result


async def divide_scenarios(text):
    prompt = f"""
请将以下文本细粒度分割成多个正交的电影场景，每个场景需要有丰富的内容描述且尽可能保留原文，内容描述需要语义连贯上下场景衔接，所有场景可以覆盖整本小说内容, 去除所有的对话内容。
每个场景的描述格式如下，内容中仅包括小说的描述，不要生成冗余信息：

{{场景[NUMBER]: 
{{标题：[TITLE]
内容：[SCENE CONTENT]}}}}

请按要求返回JSON格式响应，小说内容如下：{text}"""

    response = await client.chat.completions.create(
        model="qwen-max-2025-01-25",
        messages=[
            {"role": "system", "content": "你是一个专业的小说改编影视的编剧。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    result = response.choices[0].message.content
    try:
        cleaned = re.sub(r'^```json|```$', '', result.strip(), flags=re.MULTILINE).strip()
        json_data = json.loads(cleaned)
        async with aiofiles.open("场景分割.json", "w", encoding="utf-8") as f:
            await f.write(json.dumps(json_data, indent=2, ensure_ascii=False))
        return json_data
    except json.JSONDecodeError:
        print("返回内容不是合法的 JSON，可以考虑用正则或人工检查")
        return result


async def divide_image(text):
    prompt = f"""
    请将下面的一个场景描述，分割成若干个画面(最多5个)，你的目标是将该场景通过若干静态画面来展现，去除掉其中的人物对话部分。注意严格遵循原场景的文字描述去生成画面，不要添加任何额外信息。

    请返回JSON格式响应，键值对为"画面[NUMBER]": "[Scene Description]"
    场景描述如下：{text}
    """
    response = await client.chat.completions.create(
        model="qwen-max-2025-01-25",
        messages=[
            {"role": "system", "content": "你是一个专业的小说改编影视的编剧。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.5,
    )

    result = response.choices[0].message.content
    try:
        cleaned = re.sub(r'^```json|```$', '', result.strip(), flags=re.MULTILINE).strip()
        json_data = json.loads(cleaned)
        return json_data
    except json.JSONDecodeError:
        print("返回内容不是合法的 JSON，可以考虑用正则或人工检查")
        return result


async def save_scenarios(scenarios_json):
    """Save scenarios and create empty CSV"""
    # Save scenarios JSON
    async with aiofiles.open("场景分割.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(scenarios_json, indent=2, ensure_ascii=False))
    
    scenarios_count = len(scenarios_json)
    print(f"✅ 保存了 {scenarios_count} 个场景到 场景分割.json")

    return scenarios_json

async def async_main(text):
    print("BADAPPLE")
    
    print("🚀 开始处理...")
    # Run character extraction and scenario division concurrently
    scenarios_task = divide_scenarios(text)
    character_task = extract_character_features(text)
    
    scenarios, character_info = await asyncio.gather(scenarios_task, character_task)
    
    # Process scenarios and update config concurrently
    scenarios_processing_task = save_scenarios(scenarios)
    config_update_task = update_config_with_characters(character_info)
    
    await asyncio.gather(scenarios_processing_task, config_update_task)
    
    print("🎉 所有任务完成！")
    
    # Return the results for UI display
    return scenarios, character_info

def main(text: str):
    with open("../input.txt", "w", encoding="utf-8") as file:
        file.write(text)
    
    return asyncio.run(async_main(text))

if __name__ == '__main__':
    asyncio.run(async_main())
from openai import OpenAI
import re
import os
import json
import pandas as pd
import tqdm


client = OpenAI(
    # 如果没有配置环境变量，请用百炼API Key替换：api_key="sk-xxx"
    api_key="sk-883af3c325b140c3986f45704410f614",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def update_config_with_characters(character_data, config_path="../config.json"):
    # 加载已有 config.json
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

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
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("✅ config.json 已成功更新。")

def extract_character_features(text):
    prompt = f"""
请阅读以下中文小说文本，并识别所有明确提到的“角色”及其“特征描述”，并将结果用 JSON 结构返回。
JSON的键值对为"角色名": "xxx", "特征": "xxx"
注意：
1. 角色名应当真实在文本中出现。
2. 特征仅包括角色的数量、年龄、外貌、衣着，切记不要包含任何人物关系的描述
3. 如果人物的特征不足甚至没有的话，可以根据文本内容编造。
例子：
  {{"角色名1": "帕奇",
  "特征1": "一个20岁的黑发男子",

  "角色名2": "",
  "特征2": "",

  "角色名3": "",
  "特征3": ""}}

小说内容如下：
{text}
"""

    response = client.chat.completions.create(
        model="qwen-max-2025-01-25",  # 或 "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": "你是一个擅长文本分析的中文助手。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.5
    )

    result = response.choices[0].message.content

    # 尝试解析 JSON
    try:
        # 步骤 1：去除 Markdown 包裹符
        cleaned = re.sub(r'^```json|```$', '', result.strip(), flags=re.MULTILINE).strip()
        # 步骤 2：解析为 Python 对象
        json_data = json.loads(cleaned)
        with open("角色信息.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        return json_data
    except json.JSONDecodeError:
        print("返回内容不是合法的 JSON，可以考虑用正则或人工检查")
        return result

def divide_scenarios(text):
    prompt = f"""
请将以下文本分割成多个正交的电影场景，每个场景需要有足够丰富的内容描述且尽可能保留原文，内容描述需要语义连贯上下场景衔接，所有场景可以覆盖整本小说内容。
每个场景的描述格式如下，内容中仅包括小说的描述，不要出现其他无关信息，如果有角色的对白需要保留原文：

{{场景[NUMBER]: 
{{标题：[TITLE]
内容：[SCENE CONTENT]}}}}

请按要求返回JSON格式响应，小说内容如下：{text}"""

    response = client.chat.completions.create(
        model="qwen-max-2025-01-25",  # 或 "gpt-3.5-turbo"
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
        with open("场景分割.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        return json_data
    except json.JSONDecodeError:
        print("返回内容不是合法的 JSON，可以考虑用正则或人工检查")
        return result

def translate(text):
    response = client.chat.completions.create(
        model="deepseek-v3",  # 或 "gpt-3.5-turbo"
        messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user",
                "content": f'Translate the following text into English: "{text}". Do not directly translate, but instead translate from a third-person descriptive perspective, and complete the missing subject, predicate, object, attributive, adverbial, and complement in the text. Besides the translated result, do not include any irrelevant content or explanations in your response.',
                }],
        temperature=0.7,
    )

    result = response.choices[0].message.content
    return result

def save_scenarios(scenarios_json):
    #把场景分割以及对应的翻译存到csv里
    scenario_values = scenarios_json.values()
    rows = []
    for scenario in tqdm.tqdm(scenario_values, desc="Saving scenarios"):
        chinese_content = scenario['内容']
        english_content = translate(chinese_content)
        rows.append(
            {'Chinese Content':chinese_content, 'English Content':english_content, 'SD Content':'', 'SD Prompt':''}
        )
    df = pd.DataFrame(rows)
    df.to_csv('../txt/txt.csv', index=False)

if __name__ == '__main__':
    print("BADAPPLE")
    with open("../input.txt", "r", encoding="utf-8") as file:
        text = file.read()
        scenarios = divide_scenarios(text)
        # print(scenarios)
        save_scenarios(scenarios)
        # character_info = extract_character_features(text)
        # print(character_info)
        # update_config_with_characters(character_info)
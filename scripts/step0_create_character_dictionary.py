# %%
def update_config_with_characters(character_data, config_path="..\config.json"):
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


from openai import OpenAI
import re
import os
import json


def extract_character_features(text):
    prompt = f"""
请阅读以下中文小说文本，并识别所有明确提到的“角色名”及其“特征描述”，并将结果用 JSON 结构返回。
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
    client = OpenAI(
        # 如果没有配置环境变量，请用百炼API Key替换：api_key="sk-xxx"
        api_key="sk-db3f839bc51e459dae3aab49d1a779e2",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    response = client.chat.completions.create(
        model="qwen-plus",  # 或 "gpt-3.5-turbo"
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


if __name__ == '__main__':
    print("BADAPPLE")
    with open("../input.txt", "r", encoding="utf-8") as file:
        text = file.read()
        character_info = extract_character_features(text)
        print(character_info)
        update_config_with_characters(character_info)
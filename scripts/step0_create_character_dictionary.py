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




def extract_character_features(text):
    system_prompt = '''请阅读以下中文小说文本，并识别所有明确提到的“角色名”及其“特征描述”，并将结果用 JSON 结构返回。
    JSON的键值对为"角色名": "xxx", "特征": "xxx"
    提取规范：
    1.仅提取小说中真实出现的角色名称，不可虚构角色，请提取出所有的角色。

    2.每个角色如果在文本中经历明显成长（如婴儿、少女、成年）或变化为了不同的形态和样貌，请为每个阶段分别提取特征，名称中用括号注明阶段，如：“帕奇（儿童）”、“帕奇（成年）”、帕奇（整容后）。

    3.特征描述必须足够的具象和立体，不要出现“漂亮”，“慈祥”，“华丽”等抽象的描述，请务必包括以下信息：

    年龄段（如“十五六岁”、“约三十岁”）

    外貌（发色、发型、肤色、眼睛、身材、神态）

    衣着（服装颜色、材质、图案、饰品、鞋子等）

    4.编造补全说明：如文本未提及角色的某项外貌/服饰特征，可结合上下文风格合情合理地补全细节，避免留空，并不要出现“可能为”的字样。

    5.禁止输出人物关系、性格或心理活动（如“善良”“脾气暴躁”等）。
    例子：
      {"角色名1": "帕奇（成年）",
      "特征1": "一位身材高大的中年男子，蓄着整齐的深棕色胡须，面容威严却略带疲态，头戴镶嵌红宝石的金色王冠，身穿红黑相间的长袍，肩披白底黑点的毛皮披风，腰间悬挂金色佩剑，行走时脚步沉稳有力",

      "角色名2": "",
      "特征2": "",

      "角色名3": "",
      "特征3": ""}
    '''

    prompt = f"""小说内容如下：{text}"""

    response = client.chat.completions.create(
        model="qwen-plus",  # 或 "gpt-3.5-turbo"  "qwen-plus"
        messages=[
            {"role": "system", "content": system_prompt},
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


def divide_image(text):
    prompt = f"""
    请将下面的一个场景描述，分割成1~3个画面，你的目标是将该场景通过若干静态画面来展现，去除掉其中的人物对话部分，注意严格遵循原场景的文字描述去生成画面，不要添加任何额外信息。
    请返回JSON格式响应，键值对为"画面[NUMBER]": "[Scene Description]"
    场景描述如下：{text}
    """
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
        return json_data
    except json.JSONDecodeError:
        print("返回内容不是合法的 JSON，可以考虑用正则或人工检查")
        return result


# def translate(text):
#     response = client.chat.completions.create(
#         model="deepseek-v3",  # 或 "gpt-3.5-turbo"
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user",
#              "content": f'Translate the following text into English: "{text}". Do not directly translate, but instead translate from a third-person descriptive perspective, and complete the missing subject, predicate, object, attributive, adverbial, and complement in the text. Besides the translated result, do not include any irrelevant content or explanations in your response.',
#              }],
#         temperature=0.7,
#     )
#
#     result = response.choices[0].message.content
#     return result


def save_scenarios(scenarios_json):
    # 把场景分割以及对应的翻译存到csv里
    rows = []
    for scenario in tqdm.tqdm(scenarios_json.values(), desc="Processing scenarios"):
        chinese_content = scenario['内容']
        image_json = divide_image(chinese_content)

        # 记录每个场景对应的图像在DataFrame中的索引位置
        subimages = []
        start_index = len(rows)

        for image in tqdm.tqdm(image_json.values(), desc="Processing images"):
            # english_content = translate(image)
            rows.append(
                {'Chinese Content': image, 'Replaced Content': '', 'SD Content': '', 'SD Prompt': ''}
            )
            subimages.append(start_index)
            start_index += 1

        # 将索引列表保存到场景中
        scenario['子图索引'] = subimages

    # 将更新后的场景数据保存到本地
    with open("场景分割.json", "w", encoding="utf-8") as f:
        json.dump(scenarios_json, f, indent=2, ensure_ascii=False)
    df = pd.DataFrame(rows)
    df.to_csv('../txt/txt.csv', index=False)


if __name__ == '__main__':
    print("BADAPPLE")
    with open("../input2.txt", "r", encoding="utf-8") as file:
        text = file.read()
        scenarios = divide_scenarios(text)
        # print(scenarios)
        save_scenarios(scenarios)
        character_info = extract_character_features(text)
        # print(character_info)
        update_config_with_characters(character_info)


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

def extract_character_features(text):
    prompt = f"""小说内容如下：{text}"""
    client = OpenAI(
        # 如果没有配置环境变量，请用百炼API Key替换：api_key="sk-xxx"
        api_key="sk-db3f839bc51e459dae3aab49d1a779e2",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    # client = OpenAI(
    #     api_key="sk-cLHG0jRuBeFDE49617b9T3BLBkFJe5b79d2bDefD4Db7b9fa",
    #     base_url="https://c-z0-api-01.hash070.com/v1",
    # )

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


if __name__ == '__main__':
    print("BADAPPLE")
    with open("../input.txt", "r", encoding="utf-8") as file:
        text = file.read()
        character_info = extract_character_features(text)
        print(character_info)
        update_config_with_characters(character_info)
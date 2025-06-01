import gradio as gr
import pandas as pd
import json
import asyncio
from pathlib import Path
import sys

# Add project directories to path
project_dir = Path(__file__).parent.parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(project_dir))
sys.path.append(str(scripts_dir))

from step0_create_character_dictionary import main as step0_main
from step0_create_character_dictionary import update_config_with_characters

def run_step0(novel_text, config_path, api_key):
    """执行 Step 0: 创建角色字典"""
    try:
        # 设置 API Key
        if api_key:
            import os
            os.environ["OPENAI_API_KEY"] = api_key
        
        # 保存小说文本到 input.txt
        input_path = project_dir / "input.txt"
        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(novel_text)
        
        # 运行 Step 0 并获取返回数据
        scenarios, character_info = step0_main(novel_text)
        
        # 准备角色数据为 DataFrame
        character_data = []
        for key, value in character_info.items():
            if key.startswith("角色名") and value:
                idx = key.replace("角色名", "")
                feature_key = f"特征{idx}"
                feature_value = character_info.get(feature_key, "")
                character_data.append([f"角色名{idx}", value, f"特征{idx}", feature_value])
        
        # 准备场景数据为 DataFrame
        scenario_data = []
        for key, value in scenarios.items():
            title = value.get("标题", "")
            content = value.get("内容", "")
            scenario_data.append([key, title, content])
        
        return (
            "✅ Step 0 完成：角色字典和场景已生成", 
            pd.DataFrame(character_data, columns=["角色名Key", "角色名", "特征Key", "特征"]) if character_data else pd.DataFrame(),
            pd.DataFrame(scenario_data, columns=["场景Key", "标题", "内容"]) if scenario_data else pd.DataFrame()
        )
        
    except Exception as e:
        return f"❌ Step 0 失败: {str(e)}", pd.DataFrame(), pd.DataFrame()

def save_character_data(character_df):
    """保存角色数据到文件"""
    try:
        if character_df is None or len(character_df) == 0:
            return "❌ 没有角色数据可保存"
        
        # 重构角色数据
        character_dict = {}
        for _, row in character_df.iterrows():
            if pd.notna(row["角色名Key"]) and pd.notna(row["角色名"]):
                character_dict[row["角色名Key"]] = row["角色名"]
            if pd.notna(row["特征Key"]) and pd.notna(row["特征"]):
                character_dict[row["特征Key"]] = row["特征"]
        
        # 保存到角色信息.json
        character_file = project_dir / "scripts" / "角色信息.json"
        with open(character_file, 'w', encoding='utf-8') as f:
            json.dump(character_dict, f, ensure_ascii=False, indent=2)
        
        # 更新 config.json
        asyncio.run(update_config_with_characters(character_dict))
        
        return "✅ 角色数据已保存"
        
    except Exception as e:
        return f"❌ 保存角色数据失败: {str(e)}"

def save_scenario_data(scenario_df):
    """保存场景数据到文件"""
    try:
        if scenario_df is None or len(scenario_df) == 0:
            return "❌ 没有场景数据可保存"
        
        # 重构场景数据
        scenarios_dict = {}
        for _, row in scenario_df.iterrows():
            if pd.notna(row["场景Key"]) and pd.notna(row["标题"]) and pd.notna(row["内容"]):
                scenarios_dict[row["场景Key"]] = {
                    "标题": row["标题"],
                    "内容": row["内容"]
                }
        
        # 保存到场景分割.json
        scenario_file = project_dir / "scripts" / "场景分割.json"
        with open(scenario_file, 'w', encoding='utf-8') as f:
            json.dump(scenarios_dict, f, ensure_ascii=False, indent=2)
        
        return "✅ 场景数据已保存"
        
    except Exception as e:
        return f"❌ 保存场景数据失败: {str(e)}"

def load_existing_data():
    """加载现有的角色和场景数据"""
    character_df = pd.DataFrame()
    scenario_df = pd.DataFrame()
    
    try:
        # 加载角色数据
        character_file = project_dir / "scripts" / "角色信息.json"
        if character_file.exists():
            with open(character_file, 'r', encoding='utf-8') as f:
                character_info = json.load(f)
            
            character_data = []
            for key, value in character_info.items():
                if key.startswith("角色名") and value:
                    idx = key.replace("角色名", "")
                    feature_key = f"特征{idx}"
                    feature_value = character_info.get(feature_key, "")
                    character_data.append([f"角色名{idx}", value, f"特征{idx}", feature_value])
            
            if character_data:
                character_df = pd.DataFrame(character_data, columns=["角色名Key", "角色名", "特征Key", "特征"])
        
        # 加载场景数据
        scenario_file = project_dir / "scripts" / "场景分割.json"
        if scenario_file.exists():
            with open(scenario_file, 'r', encoding='utf-8') as f:
                scenarios = json.load(f)
            
            scenario_data = []
            for key, value in scenarios.items():
                title = value.get("标题", "") if isinstance(value, dict) else ""
                content = value.get("内容", "") if isinstance(value, dict) else ""
                scenario_data.append([key, title, content])
            
            if scenario_data:
                scenario_df = pd.DataFrame(scenario_data, columns=["场景Key", "标题", "内容"])
                
    except Exception as e:
        print(f"加载现有数据时出错: {e}")
    
    return character_df, scenario_df

def create_interface():
    with gr.TabItem("📚 Step 0: 角色字典"):
        gr.Markdown("### 分析小说文本，提取角色信息和场景划分")
        
        with gr.Row():
            with gr.Column():
                step0_novel_text = gr.Textbox(
                    label="小说全文",
                    placeholder="请输入完整的小说内容，脚本将自动分析场景和角色...",
                    lines=15
                )
                step0_api_key = gr.Textbox(
                    label="OpenAI API Key", 
                    placeholder="sk-...",
                    type="password"
                )
                step0_config_path = gr.Textbox(
                    label="配置文件路径（可选）",
                    placeholder="默认: ../config.json"
                )
                
                with gr.Row():
                    step0_btn = gr.Button("执行 Step 0", variant="primary")
                    load_btn = gr.Button("加载现有数据", variant="secondary")
            
            with gr.Column():
                step0_output = gr.Textbox(label="执行结果", lines=3)
        
        # 角色数据编辑区域
        gr.Markdown("### 🎭 角色信息编辑")
        character_dataframe = gr.Dataframe(
            label="角色数据（可编辑）",
            headers=["角色名Key", "角色名", "特征Key", "特征"],
            datatype=["str", "str", "str", "str"],
            interactive=True,
            wrap=True
        )
        
        with gr.Row():
            save_character_btn = gr.Button("💾 保存角色数据", variant="primary")
            character_save_result = gr.Textbox(label="保存结果", lines=1)
        
        # 场景数据编辑区域
        gr.Markdown("### 🎬 场景信息编辑")
        scenario_dataframe = gr.Dataframe(
            label="场景数据（可编辑）",
            headers=["场景Key", "标题", "内容"],
            datatype=["str", "str", "str"],
            interactive=True,
            wrap=True
        )
        
        with gr.Row():
            save_scenario_btn = gr.Button("💾 保存场景数据", variant="primary")
            scenario_save_result = gr.Textbox(label="保存结果", lines=1)
        
        # 绑定事件
        step0_btn.click(
            fn=run_step0,
            inputs=[step0_novel_text, step0_config_path, step0_api_key],
            outputs=[step0_output, character_dataframe, scenario_dataframe]
        )
        
        load_btn.click(
            fn=load_existing_data,
            inputs=[],
            outputs=[character_dataframe, scenario_dataframe]
        )
        
        save_character_btn.click(
            fn=save_character_data,
            inputs=[character_dataframe],
            outputs=[character_save_result]
        )
        
        save_scenario_btn.click(
            fn=save_scenario_data,
            inputs=[scenario_dataframe],
            outputs=[scenario_save_result]
        )
    
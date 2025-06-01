import gradio as gr
import os
import json
import pandas as pd
import asyncio
from pathlib import Path
import sys

# 添加当前目录和 scripts 目录到 Python 路径
project_dir = Path(__file__).parent.parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(project_dir))
sys.path.append(str(scripts_dir))

def set_api_key(api_key):
    """设置 OpenAI API Key"""
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        return "✅ API Key 已设置"
    return "❌ 请输入有效的 API Key"

def run_step1(min_sentence_length, trigger_word, api_key):
    """执行 Step 1: 提取关键词（移除文件上传）"""
    try:
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # 更新配置
        config_path = project_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config["句子最小长度限制"] = min_sentence_length
            if trigger_word:
                config["引导词"] = trigger_word
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        
        from step1_extract_keywords import main as step1_main
        result = step1_main()
        return "✅ Step 1 完成：关键词提取完成", get_storyboard_data()
        
    except Exception as e:
        return f"❌ Step 1 失败: {str(e)}", pd.DataFrame()

def get_storyboard_data():
    """获取分镜脚本数据用于显示"""
    try:
        from step1_extract_keywords import get_current_storyboards
        return get_current_storyboards()
    except Exception as e:
        print(f"获取分镜数据失败: {e}")
        return pd.DataFrame()

def regenerate_storyboards(storyboard_df, trigger_word):
    """重新生成选中的分镜脚本"""
    try:
        # 检查是否有数据
        if storyboard_df is None or len(storyboard_df) == 0:
            return "❌ 没有可用的分镜数据", pd.DataFrame()
        
        # 获取用户选择的行（Gradio DataFrame 的选择机制）
        # 这里我们简化处理：让用户通过输入序号来选择
        return "⚠️ 请使用下方的序号选择功能重新生成分镜", storyboard_df
        
    except Exception as e:
        return f"❌ 重新生成失败: {str(e)}", pd.DataFrame()

def regenerate_storyboards_by_indices(indices_text, trigger_word):
    """通过序号重新生成分镜脚本"""
    try:
        if not indices_text.strip():
            return "❌ 请输入要重新生成的序号（例如：0,1,2 或 0-5）", get_storyboard_data()
        
        # 解析用户输入的序号
        selected_indices = []
        for part in indices_text.split(','):
            part = part.strip()
            if '-' in part:
                # 处理范围 (例如 0-5)
                start, end = map(int, part.split('-'))
                selected_indices.extend(range(start, end + 1))
            else:
                # 处理单个序号
                selected_indices.append(int(part))
        
        # 去重并排序
        selected_indices = sorted(list(set(selected_indices)))
        
        # 导入异步函数并运行
        async def run_regenerate():
            from step1_extract_keywords import regenerate_selected_storyboards, default_trigger
            
            # 使用默认引导词如果用户没有提供
            trigger = trigger_word if trigger_word.strip() else default_trigger
            
            return await regenerate_selected_storyboards(selected_indices, trigger)
        
        result = asyncio.run(run_regenerate())
        return result, get_storyboard_data()
        
    except ValueError as e:
        return f"❌ 序号格式错误: {str(e)}", get_storyboard_data()
    except Exception as e:
        return f"❌ 重新生成失败: {str(e)}", get_storyboard_data()

def create_interface():
    """创建 Step 1 的 Gradio 界面"""
    with gr.TabItem("🔍 Step 1: 关键词提取"):
        gr.Markdown("### 提取场景关键词，生成 Stable Diffusion 提示词")
        
        with gr.Row():
            with gr.Column():
                step1_api_key = gr.Textbox(
                    label="OpenAI API Key",
                    placeholder="sk-...",
                    type="password"
                )
                step1_min_length = gr.Slider(
                    label="句子最小长度限制",
                    minimum=50,
                    maximum=200,
                    value=100,
                    step=10
                )
                step1_trigger = gr.Textbox(
                    label="引导词（可选）",
                    placeholder="留空使用默认引导词...",
                    lines=3
                )
                
                with gr.Row():
                    step1_btn = gr.Button("执行 Step 1", variant="primary")
                    load_storyboard_btn = gr.Button("加载现有数据", variant="secondary")
            
            with gr.Column():
                step1_output = gr.Textbox(label="执行结果", lines=5)
        
        # 分镜脚本数据显示和编辑区域
        gr.Markdown("### 🎬 分镜脚本管理")
        
        storyboard_dataframe = gr.Dataframe(
            label="分镜脚本数据",
            headers=["序号", "中文内容", "英文翻译", "分镜脚本"],
            datatype=["number", "str", "str", "str"],
            interactive=False,  # 设为只读
            wrap=True,
            value=pd.DataFrame(columns=["序号", "中文内容", "英文翻译", "分镜脚本"])
        )
        
        # 重新生成区域
        gr.Markdown("### 🔄 选择性重新生成")
        
        with gr.Row():
            with gr.Column():
                regenerate_indices = gr.Textbox(
                    label="要重新生成的序号",
                    placeholder="例如：0,1,2 或 0-5 或 0,3-7,10",
                    info="输入要重新生成的分镜序号，支持单个数字、逗号分隔或范围表示"
                )
                regenerate_trigger = gr.Textbox(
                    label="重新生成引导词（可选）",
                    placeholder="留空使用默认引导词...",
                    lines=2
                )
                regenerate_btn = gr.Button("🔄 重新生成指定分镜", variant="secondary")
                
            with gr.Column():
                regenerate_output = gr.Textbox(label="重新生成结果", lines=5)
        
        gr.Markdown("""
        **使用说明：**
        1. 先执行 Step 1 生成初始分镜脚本
        2. 查看上方表格中的分镜效果，记录需要重新生成的序号
        3. 在「要重新生成的序号」中输入序号，支持以下格式：
           - 单个序号：`0` 或 `3`
           - 多个序号：`0,1,2` 或 `0,3,7`
           - 序号范围：`0-5` 表示从0到5
           - 混合格式：`0,3-7,10` 表示序号0、3到7、10
        4. 可选择性修改引导词，然后点击「重新生成指定分镜」
        5. 系统将只重新生成指定的分镜脚本，节省时间
        """)
        
        # 绑定事件
        step1_btn.click(
            fn=run_step1,
            inputs=[step1_min_length, step1_trigger, step1_api_key],
            outputs=[step1_output, storyboard_dataframe]
        )
        
        load_storyboard_btn.click(
            fn=get_storyboard_data,
            inputs=[],
            outputs=[storyboard_dataframe]
        )
        
        regenerate_btn.click(
            fn=regenerate_storyboards_by_indices,
            inputs=[regenerate_indices, regenerate_trigger],
            outputs=[regenerate_output, storyboard_dataframe]
        )
        
        return {
            'step1_api_key': step1_api_key,
            'step1_min_length': step1_min_length,
            'step1_trigger': step1_trigger,
            'step1_btn': step1_btn,
            'step1_output': step1_output,
            'storyboard_dataframe': storyboard_dataframe,
            'regenerate_indices': regenerate_indices,
            'regenerate_trigger': regenerate_trigger,
            'regenerate_btn': regenerate_btn,
            'regenerate_output': regenerate_output
        }
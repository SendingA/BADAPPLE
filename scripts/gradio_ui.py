import gradio as gr
import os
import json
import subprocess
import sys
from pathlib import Path
import pandas as pd
import asyncio

# 添加当前目录和 scripts 目录到 Python 路径
project_dir = Path(__file__).parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(project_dir))
sys.path.append(str(scripts_dir))

gr.set_static_paths([str(project_dir)])

# 导入各个步骤的模块
try:
    import gradio_utils.step0
    import gradio_utils.step1
    import gradio_utils.step2
    import gradio_utils.step3
    import gradio_utils.step4  # 添加这行
    
    # 移除直接导入 step4_main
    # from step4_output_video import main as step4_main
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有脚本文件存在于 scripts 目录中")


def run_all_steps(novel_text, api_key, server_urls_text, max_workers, min_sentence_length, width, height, steps, fps):
    """一键运行所有步骤（支持多服务器）"""
    results = []
    
    # Step 0
    result0, chars, scenarios = gradio_utils.step0.run_step0(novel_text, "", api_key)
    results.append(f"Step 0: {result0}")
    
    if "失败" in result0:
        return "\n".join(results)
    
    # Step 1
    result1, _ = gradio_utils.step1.run_step1(min_sentence_length, "", api_key)
    results.append(f"Step 1: {result1}")
    
    if "失败" in result1:
        return "\n".join(results)
    
    # Step 2 (多服务器)
    result2, _ = gradio_utils.step2.run_step2(
        server_urls_text, max_workers, width, height, steps, "DPM++ 3M SDE", 
        "Karras", 7, -1, True, 2, "Latent", 0.7, "", "", None
    )
    results.append(f"Step 2: {result2}")
    
    if "失败" in result2:
        return "\n".join(results)
    
    # Step 3
    result3, _, _ = gradio_utils.step3.run_step3_for_all("zh", "zf")
    results.append(f"Step 3: {result3}")
    
    if "失败" in result3:
        return "\n".join(results)
    
    # Step 4 - 使用新的模块化版本
    result4 = gradio_utils.step4.run_step4_for_all(fps, True, True, "fade")
    results.append(f"Step 4: {result4}")
    
    return "\n".join(results)


def create_one_click_interface():
    with gr.TabItem("🚀 一键生成"):
        gr.Markdown("### 快速生成模式（支持多服务器并行）")
        
        with gr.Row():
            with gr.Column():
                quick_novel_text = gr.Textbox(
                    label="小说文本",
                    placeholder="请输入完整的小说内容...",
                    lines=10
                )
                quick_api_key = gr.Textbox(
                    label="OpenAI API Key",
                    placeholder="sk-...",
                    type="password"
                )
                quick_server_urls = gr.Textbox(
                    label="WebUI 服务器地址（每行一个）",
                    value="http://localhost:7860\nhttp://localhost:7861",
                    placeholder="http://server1:7860\nhttp://server2:7861",
                    lines=3
                )
                quick_max_workers = gr.Number(
                    label="最大并行数",
                    value=2,
                )
                
            with gr.Column():
                quick_min_length = gr.Slider(
                    label="最小句子长度",
                    minimum=50,
                    maximum=200,
                    value=100,
                    step=10
                )
                quick_width = gr.Number(label="图像宽度", value=512)
                quick_height = gr.Number(label="图像高度", value=512)
                quick_steps = gr.Slider(label="生成步数", minimum=10, maximum=100, value=50)
                quick_fps = gr.Slider(label="视频帧率", minimum=15, maximum=60, value=30)
        
        quick_run_btn = gr.Button("🚀 开始生成", variant="primary", size="lg")
        quick_output = gr.Textbox(label="执行结果", lines=5)
        
        quick_run_btn.click(
            fn=run_all_steps,
            inputs=[quick_novel_text, quick_api_key, quick_server_urls, quick_max_workers,
                quick_min_length, quick_width, quick_height, quick_steps, quick_fps],
            outputs=quick_output
        )

# 创建 Gradio 界面
with gr.Blocks(title="BADAPPLE", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 BADAPPLE")
    gr.Markdown("将小说文本转换为带配音的视频，支持角色识别、图像生成、语音合成等功能")
    
    with gr.Tabs():
        # 在一键生成界面中添加多服务器配置
        create_one_click_interface()
        
        # Step 0 标签页
        gradio_utils.step0.create_interface()
  
        # Step 1 标签页
        gradio_utils.step1.create_interface()

        # Step 2 标签页
        gradio_utils.step2.create_interface()
        
        # Step 3 标签页 - 现在由 step3.py 处理
        gradio_utils.step3.create_interface()
        
        # Step 4 标签页 - 现在由 step4.py 处理
        gradio_utils.step4.create_interface()
        
        # 帮助标签页
        with gr.TabItem("❓ 使用说明"):
            gr.Markdown("""
            ## 使用流程
            
            ### 🚀 一键生成（推荐新手）
            1. 在「一键生成」页面输入小说文本和必要参数
            2. 点击「开始生成」，系统将自动完成所有步骤
            3. 等待处理完成，最终视频将保存在 `../video` 目录
            
            ### 🔧 分步骤执行（高级用户）
            1. **Step 0**: 输入小说全文，生成角色字典
            2. **Step 1**: 提取关键词，生成 AI 绘图提示词
            3. **Step 2**: 根据提示词生成场景图像
            4. **Step 3**: 为每个场景生成配音
            5. **Step 4**: 合成最终视频
            
            ## 注意事项
            
            - **API Key**: 需要有效的 OpenAI API Key 用于文本分析
            - **WebUI**: Step 2 需要运行 Automatic1111 WebUI 服务
            - **语音**: Step 3 需要 Kokoro TTS 模型文件
            - **文件路径**: 确保相关目录存在且有写入权限
            
            ## 系统要求
            
            - Python 3.8+
            - 足够的磁盘空间（图像和视频文件较大）
            - 稳定的网络连接（API 调用）
            - CUDA 兼容显卡（推荐）
            """)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7870,
        share=False,
        debug=True,
        allowed_paths=[
            str(project_dir), 
            str(scripts_dir),
            str(Path(project_dir) / "image"),
            str(Path(project_dir) / "temp"),
            str(Path(project_dir) / "voice"),
            str(Path(project_dir) / "video")
        ]
    )
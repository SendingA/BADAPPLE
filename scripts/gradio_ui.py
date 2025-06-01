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
    
    from step3_txt_to_voice_kokoro import main as step3_main
    from step4_output_video import main as step4_main
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有脚本文件存在于 scripts 目录中")


def run_step3(input_file, output_dir, language, gender):
    """执行 Step 3: 文本转语音"""
    try:
        # 准备参数
        input_file = input_file or str(project_dir / "scripts" / "场景分割.json")
        output_dir = output_dir or str(project_dir / "voice")
        
        success, audio_files = step3_main(input_file, output_dir, language, gender)
        
        if success and audio_files:
            # 返回第一个音频文件用于预览，以及所有文件的信息
            first_audio = audio_files[0] if audio_files else None
            result_text = f"✅ Step 3 完成：成功生成 {len(audio_files)} 个音频文件\n"
            result_text += "生成的文件:\n"
            for i, file_path in enumerate(audio_files):
                result_text += f"  {i+1}. {os.path.basename(file_path)}\n"
            
            return result_text, first_audio, audio_files
        else:
            return "❌ Step 3 失败: 未生成音频文件", None, []
        
    except Exception as e:
        return f"❌ Step 3 失败: {str(e)}", None, []

def load_existing_audio(voice_dir):
    """加载现有的音频文件"""
    try:
        voice_dir = voice_dir or str(project_dir / "voice")
        
        if not os.path.exists(voice_dir):
            return "❌ 音频目录不存在", None, []
        
        # 查找所有 .wav 文件
        audio_files = []
        for file in os.listdir(voice_dir):
            if file.lower().endswith('.wav'):
                audio_files.append(os.path.join(voice_dir, file))
        
        # 按文件名排序
        audio_files.sort()
        
        if not audio_files:
            return "❌ 未找到音频文件", None, []
        
        # 返回第一个音频文件用于预览
        first_audio = audio_files[0]
        result_text = f"✅ 找到 {len(audio_files)} 个音频文件\n"
        result_text += "现有文件:\n"
        for i, file_path in enumerate(audio_files):
            result_text += f"  {i+1}. {os.path.basename(file_path)}\n"
        
        return result_text, first_audio, audio_files
        
    except Exception as e:
        return f"❌ 加载失败: {str(e)}", None, []

def preview_audio(audio_files, selected_index):
    """预览选中的音频文件"""
    try:
        if audio_files and 0 <= selected_index < len(audio_files):
            return audio_files[selected_index]
        return None
    except:
        return None

def run_step4(fps, enlarge_background, enable_effect, effect_type):
    """执行 Step 4: 输出视频"""
    try:
        # 更新配置
        config_path = project_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config.update({
                "fps": fps,
                "enlarge_background": enlarge_background,
                "enable_effect": enable_effect,
                "effect_type": effect_type
            })
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        
        result = step4_main()
        return "✅ Step 4 完成：视频生成完成"
        
    except Exception as e:
        return f"❌ Step 4 失败: {str(e)}"

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
    result3, _, _ = run_step3("", "", "zh", "zf")
    results.append(f"Step 3: {result3}")
    
    if "失败" in result3:
        return "\n".join(results)
    
    # Step 4
    result4 = run_step4(fps, True, True, 0)
    results.append(f"Step 4: {result4}")
    


# 创建 Gradio 界面
with gr.Blocks(title="小说转视频生成器", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 小说转视频生成器")
    gr.Markdown("将小说文本转换为带配音的视频，支持角色识别、图像生成、语音合成等功能")
    
    with gr.Tabs():
        # 在一键生成界面中添加多服务器配置
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
                        value="http://172.18.36.54:7862\nhttp://172.18.36.54:7863\nhttp://172.18.36.54:7864\nhttp://172.18.36.54:7865\nhttp://172.18.36.54:7866",
                        placeholder="http://server1:7860\nhttp://server2:7861",
                        lines=3
                    )
                    quick_max_workers = gr.Number(
                        label="最大并行数",
                        value=2,
                        minimum=1,
                        maximum=8
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

        
        # Step 0 标签页
        gradio_utils.step0.create_interface()
  
        # Step 1 标签页
        gradio_utils.step1.create_interface()

        # Step 2 标签页
        gradio_utils.step2.create_interface()
        
        # Step 3 标签页
        with gr.TabItem("🎵 Step 3: 语音合成"):
            gr.Markdown("### 为场景生成配音")
            
            with gr.Row():
                with gr.Column():
                    step3_input_file = gr.Textbox(
                        label="输入文件路径（可选）",
                        placeholder="默认: ../scripts/场景分割.json"
                    )
                    step3_output_dir = gr.Textbox(
                        label="输出目录（可选）",
                        placeholder="默认: ../voice"
                    )
                    step3_language = gr.Dropdown(
                        label="语言",
                        choices=["zh", "en"],
                        value="zh"
                    )
                    step3_gender = gr.Radio(
                        label="声音性别",
                        choices=[("女声", "zf"), ("男声", "zm")],
                        value="zf"
                    )
                    
                    with gr.Row():
                        step3_btn = gr.Button("🎤 生成语音", variant="primary")
                        step3_load_btn = gr.Button("📁 加载现有音频", variant="secondary")
                
                with gr.Column():
                    step3_output = gr.Textbox(label="执行结果", lines=8)
                    
                    # 音频预览区域
                    gr.Markdown("### 🎵 音频预览")
                    step3_audio_preview = gr.Audio(
                        label="音频预览",
                        type="filepath",
                        interactive=False
                    )
                    
                    # 音频文件选择
                    step3_audio_selector = gr.Slider(
                        label="选择音频文件（1开始）",
                        minimum=1,
                        maximum=10,
                        value=1,
                        step=1,
                        visible=False
                    )
                    
                    # 音频文件信息显示
                    with gr.Row():
                        step3_current_file = gr.Textbox(
                            label="当前文件",
                            interactive=False,
                            visible=False
                        )
            
            # 隐藏的状态变量用于存储音频文件列表
            step3_audio_files = gr.State([])
            
            # 生成语音按钮的回调
            step3_btn.click(
                fn=run_step3,
                inputs=[step3_input_file, step3_output_dir, step3_language, step3_gender],
                outputs=[step3_output, step3_audio_preview, step3_audio_files]
            ).then(
                fn=lambda files: [
                    gr.update(
                        visible=len(files) > 1,
                        maximum=len(files) if files else 1,
                        value=1
                    ),
                    gr.update(
                        value=os.path.basename(files[0]) if files else "",
                        visible=len(files) > 0
                    )
                ],
                inputs=[step3_audio_files],
                outputs=[step3_audio_selector, step3_current_file]
            )
            
            # 加载现有音频按钮的回调
            step3_load_btn.click(
                fn=load_existing_audio,
                inputs=[step3_output_dir],
                outputs=[step3_output, step3_audio_preview, step3_audio_files]
            ).then(
                fn=lambda files: [
                    gr.update(
                        visible=len(files) > 1,
                        maximum=len(files) if files else 1,
                        value=1
                    ),
                    gr.update(
                        value=os.path.basename(files[0]) if files else "",
                        visible=len(files) > 0
                    )
                ],
                inputs=[step3_audio_files],
                outputs=[step3_audio_selector, step3_current_file]
            )
            
            # 音频选择器的回调
            step3_audio_selector.change(
                fn=lambda files, idx: [
                    preview_audio(files, int(idx)-1) if files else None,
                    os.path.basename(files[int(idx)-1]) if files and 0 <= int(idx)-1 < len(files) else ""
                ],
                inputs=[step3_audio_files, step3_audio_selector],
                outputs=[step3_audio_preview, step3_current_file]
            )
        
        # Step 4 标签页
        with gr.TabItem("🎬 Step 4: 视频输出"):
            gr.Markdown("### 合成最终视频")
            
            with gr.Row():
                with gr.Column():
                    step4_fps = gr.Slider(
                        label="视频帧率",
                        minimum=15,
                        maximum=60,
                        value=30,
                        step=1
                    )
                    step4_enlarge = gr.Checkbox(
                        label="放大背景",
                        value=True
                    )
                    step4_enable_effect = gr.Checkbox(
                        label="启用特效",
                        value=True
                    )
                    step4_effect_type = gr.Dropdown(
                        label="特效类型",
                        choices=[("Ken Burns", 0), ("淡入淡出", 1)],
                        value=0
                    )
                
                with gr.Column():
                    step4_output = gr.Textbox(label="执行结果", lines=10)
            
            step4_btn = gr.Button("执行 Step 4", variant="secondary")
            step4_btn.click(
                fn=run_step4,
                inputs=[step4_fps, step4_enlarge, step4_enable_effect, step4_effect_type],
                outputs=step4_output
            )
        
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
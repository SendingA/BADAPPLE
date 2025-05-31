import gradio as gr
import os
import json
import subprocess
import sys
from pathlib import Path

# 添加当前目录和 scripts 目录到 Python 路径
project_dir = Path(__file__).parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(project_dir))
sys.path.append(str(scripts_dir))

# 导入各个步骤的模块
try:
    from step0_create_character_dictionary import main as step0_main
    from step1_extract_keywords import main as step1_main
    from step2_txt_to_image_webui import main as step2_main
    from step3_txt_to_voice_kokoro import main as step3_main
    from step4_output_video import main as step4_main
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有脚本文件存在于 scripts 目录中")

def set_api_key(api_key):
    """设置 OpenAI API Key"""
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        return "✅ API Key 已设置"
    return "❌ 请输入有效的 API Key"

def run_step0(novel_text, config_path, api_key):
    """执行 Step 0: 创建角色字典"""
    try:
        # 设置 API Key
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # 保存小说文本到 input.txt
        input_path = project_dir / "input.txt"
        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(novel_text)
        
        # 运行 Step 0
        result = step0_main(novel_text)
        
        # 读取生成的角色信息
        config_file = project_dir / "config.json"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            characters = [config.get(f"角色名{i}", "") for i in range(1, 11)]
            return "✅ Step 0 完成：角色字典已生成", "\n".join([f"角色{i}: {char}" for i, char in enumerate(characters, 1) if char])
        
        return "✅ Step 0 完成", "角色信息将显示在这里"
        
    except Exception as e:
        return f"❌ Step 0 失败: {str(e)}", ""

def run_step1(input_file, min_sentence_length, trigger_word, api_key):
    """执行 Step 1: 提取关键词"""
    try:
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        # 如果有上传文件，保存为 input.docx
        if input_file:
            input_path = project_dir / "input.docx"
            with open(input_path, 'wb') as f:
                f.write(input_file)
        
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
        
        result = step1_main()
        return "✅ Step 1 完成：关键词提取完成"
        
    except Exception as e:
        return f"❌ Step 1 失败: {str(e)}"

def run_step2(webui_url, width, height, steps, sampler, scheduler, cfg_scale, seed, 
              enable_hr, hr_scale, hr_upscaler, denoising_strength, 
              more_details, negative_prompt, control_image):
    """执行 Step 2: 文本转图像"""
    try:
        # 设置环境变量
        if webui_url:
            os.environ["WEBUI_SERVER_URL"] = webui_url
        
        # 更新配置
        config_path = project_dir / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新图像生成参数
            config.update({
                "width": width,
                "height": height,
                "steps": steps,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "cfg_scale": cfg_scale,
                "seed": seed if seed != -1 else -1,
                "enable_hr": enable_hr,
                "hr_scale": hr_scale,
                "hr_upscaler": hr_upscaler,
                "denoising_strength": denoising_strength
            })
            
            if more_details:
                config["更多正面细节"] = more_details
            if negative_prompt:
                config["负面提示"] = negative_prompt
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 处理控制图
        if control_image:
            control_path = project_dir / "control_image.png"
            control_image.save(control_path)
        
        result = step2_main()
        return "✅ Step 2 完成：图像生成完成"
        
    except Exception as e:
        return f"❌ Step 2 失败: {str(e)}"

def run_step3(input_file, output_dir, language, gender):
    """执行 Step 3: 文本转语音"""
    try:
        # 准备参数
        args = [
            "--input_file", input_file or str(project_dir / "scripts" / "场景分割.json"),
            "--output_dir", output_dir or str(project_dir / "voice"),
            "--language", language,
            "--gender", gender
        ]
        
        result = step3_main()
        return "✅ Step 3 完成：语音生成完成"
        
    except Exception as e:
        return f"❌ Step 3 失败: {str(e)}"

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

def run_all_steps(novel_text, api_key, webui_url, min_sentence_length, width, height, steps, fps):
    """一键运行所有步骤"""
    results = []
    
    # Step 0
    result0, chars = run_step0(novel_text, "", api_key)
    results.append(f"Step 0: {result0}")
    
    if "失败" in result0:
        return "\n".join(results)
    
    # Step 1
    result1 = run_step1(None, min_sentence_length, "", api_key)
    results.append(f"Step 1: {result1}")
    
    if "失败" in result1:
        return "\n".join(results)
    
    # Step 2
    result2 = run_step2(webui_url, width, height, steps, "DPM++ 3M SDE", "Karras", 7, -1,
                       True, 2, "Latent", 0.7, "", "", None)
    results.append(f"Step 2: {result2}")
    
    if "失败" in result2:
        return "\n".join(results)
    
    # Step 3
    result3 = run_step3("", "", "zh", "zf")
    results.append(f"Step 3: {result3}")
    
    if "失败" in result3:
        return "\n".join(results)
    
    # Step 4
    result4 = run_step4(fps, True, True, 0)
    results.append(f"Step 4: {result4}")
    
    return "\n".join(results)

# 创建 Gradio 界面
with gr.Blocks(title="小说转视频生成器", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 小说转视频生成器")
    gr.Markdown("将小说文本转换为带配音的视频，支持角色识别、图像生成、语音合成等功能")
    
    with gr.Tabs():
        # 一键生成标签页
        with gr.TabItem("🚀 一键生成"):
            gr.Markdown("### 快速生成模式（使用默认参数）")
            
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
                    quick_webui_url = gr.Textbox(
                        label="WebUI 服务器地址",
                        value="http://172.18.36.54:7862",
                        placeholder="http://localhost:7860"
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
                inputs=[quick_novel_text, quick_api_key, quick_webui_url, quick_min_length, 
                       quick_width, quick_height, quick_steps, quick_fps],
                outputs=quick_output
            )
        
        # Step 0 标签页
        with gr.TabItem("📚 Step 0: 角色字典"):
            gr.Markdown("### 分析小说文本，提取角色信息")
            
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
                
                with gr.Column():
                    step0_output = gr.Textbox(label="执行结果", lines=3)
                    step0_characters = gr.Textbox(
                        label="识别的角色",
                        placeholder="角色信息将在这里显示...",
                        lines=10
                    )
            
            step0_btn = gr.Button("执行 Step 0", variant="primary")
            step0_btn.click(
                fn=run_step0,
                inputs=[step0_novel_text, step0_config_path, step0_api_key],
                outputs=[step0_output, step0_characters]
            )
        
        # Step 1 标签页
        with gr.TabItem("🔍 Step 1: 关键词提取"):
            gr.Markdown("### 提取场景关键词，生成 Stable Diffusion 提示词")
            
            with gr.Row():
                with gr.Column():
                    step1_file = gr.File(
                        label="上传文档（可选）",
                        file_types=[".docx"]
                    )
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
                        placeholder="留空使用默认引导词..."
                    )
                
                with gr.Column():
                    step1_output = gr.Textbox(label="执行结果", lines=10)
            
            step1_btn = gr.Button("执行 Step 1", variant="primary")
            step1_btn.click(
                fn=run_step1,
                inputs=[step1_file, step1_min_length, step1_trigger, step1_api_key],
                outputs=step1_output
            )
        
        # Step 2 标签页
        with gr.TabItem("🎨 Step 2: 图像生成"):
            gr.Markdown("### 根据提示词生成场景图像")
            
            with gr.Row():
                with gr.Column():
                    step2_webui_url = gr.Textbox(
                        label="WebUI 服务器地址",
                        value="http://172.18.36.54:7862",
                        placeholder="http://localhost:7860"
                    )
                    
                    with gr.Row():
                        step2_width = gr.Number(label="宽度", value=512)
                        step2_height = gr.Number(label="高度", value=512)
                    
                    step2_steps = gr.Slider(label="生成步数", minimum=10, maximum=100, value=50)
                    step2_sampler = gr.Dropdown(
                        label="采样器",
                        choices=["DPM++ 3M SDE", "DPM++ 2M", "Euler a", "DDIM"],
                        value="DPM++ 3M SDE"
                    )
                    step2_scheduler = gr.Dropdown(
                        label="调度器",
                        choices=["Karras", "Exponential", "Normal"],
                        value="Karras"
                    )
                    step2_cfg = gr.Slider(label="CFG Scale", minimum=1, maximum=20, value=7)
                    step2_seed = gr.Number(label="随机种子（-1=随机）", value=-1)
                
                with gr.Column():
                    step2_enable_hr = gr.Checkbox(label="启用高分辨率修复", value=True)
                    step2_hr_scale = gr.Slider(label="放大倍数", minimum=1, maximum=4, value=2, step=0.1)
                    step2_hr_upscaler = gr.Dropdown(
                        label="放大算法",
                        choices=["Latent", "ESRGAN_4x", "R-ESRGAN 4x+"],
                        value="Latent"
                    )
                    step2_denoising = gr.Slider(label="去噪强度", minimum=0, maximum=1, value=0.7, step=0.05)
                    
                    step2_more_details = gr.Textbox(label="额外正面提示（可选）")
                    step2_negative = gr.Textbox(label="负面提示（可选）")
                    step2_control_image = gr.Image(label="控制图（可选）", type="pil")
            
            step2_output = gr.Textbox(label="执行结果", lines=5)
            step2_btn = gr.Button("执行 Step 2", variant="primary")
            step2_btn.click(
                fn=run_step2,
                inputs=[step2_webui_url, step2_width, step2_height, step2_steps, step2_sampler,
                       step2_scheduler, step2_cfg, step2_seed, step2_enable_hr, step2_hr_scale,
                       step2_hr_upscaler, step2_denoising, step2_more_details, step2_negative, step2_control_image],
                outputs=step2_output
            )
        
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
                
                with gr.Column():
                    step3_output = gr.Textbox(label="执行结果", lines=10)
            
            step3_btn = gr.Button("执行 Step 3", variant="primary")
            step3_btn.click(
                fn=run_step3,
                inputs=[step3_input_file, step3_output_dir, step3_language, step3_gender],
                outputs=step3_output
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
            
            step4_btn = gr.Button("执行 Step 4", variant="primary")
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
        debug=True
    )
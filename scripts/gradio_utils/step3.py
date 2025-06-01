import gradio as gr
import os
import sys
from pathlib import Path

# 添加项目路径
project_dir = Path(__file__).parent.parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(project_dir))
sys.path.append(str(scripts_dir))

try:
    from step3_txt_to_voice_kokoro import main as step3_main
except ImportError as e:
    print(f"导入 step3_txt_to_voice_kokoro 失败: {e}")

def run_step3(language, gender):
    """执行 Step 3: 文本转语音"""
    try:
        # 使用固定的路径
        input_file = str(project_dir / "scripts" / "场景分割.json")
        output_dir = str(project_dir / "voice")
        
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

def load_existing_audio():
    """加载现有的音频文件"""
    try:
        voice_dir = str(project_dir / "voice")
        
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

def create_interface():
    """创建 Step 3 的 Gradio 界面"""
    with gr.TabItem("🎵 Step 3: 语音合成"):
        gr.Markdown("### 为场景生成配音")
        
        with gr.Row():
            with gr.Column():
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
            inputs=[step3_language, step3_gender],
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
            inputs=[],
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

def run_step3_for_all(language="zh", gender="zf"):
    """供一键生成调用的简化版本"""
    return run_step3(language, gender)
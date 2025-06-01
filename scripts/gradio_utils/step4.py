import gradio as gr
import os
import sys
import json
from pathlib import Path

# 添加项目路径
project_dir = Path(__file__).parent.parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(project_dir))
sys.path.append(str(scripts_dir))

try:
    from step4_output_video import main as step4_main
except ImportError as e:
    print(f"导入 step4_output_video 失败: {e}")

def get_config():
    """获取配置文件"""
    config_file = project_dir / 'config.json'
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def update_config(fps, enlarge_background, enable_effect, effect_type):
    """更新配置文件"""
    try:
        config_file = project_dir / 'config.json'
        
        # 读取现有配置
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # 更新配置
        config.update({
            "fps": fps,
            "enlarge_background": enlarge_background,
            "enable_effect": enable_effect,
            "effect_type": effect_type
        })
        
        # 保存配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"更新配置失败: {e}")
        return False

def run_step4(fps, enlarge_background, enable_effect, effect_type):
    """执行 Step 4: 输出视频"""
    try:
        # 更新配置
        if not update_config(fps, enlarge_background, enable_effect, effect_type):
            return "❌ Step 4 失败: 无法更新配置文件", None
        
        # 检查必要的输入文件
        scenarios_file = project_dir / "scripts" / "场景分割.json"
        voice_dir = project_dir / "voice"
        image_dir = project_dir / "image"
        
        if not scenarios_file.exists():
            return "❌ Step 4 失败: 场景分割文件不存在，请先完成 Step 1", None
        
        if not voice_dir.exists() or not any(voice_dir.glob("*.wav")):
            return "❌ Step 4 失败: 音频文件不存在，请先完成 Step 3", None
        
        if not image_dir.exists() or not any(image_dir.glob("output_*")):
            return "❌ Step 4 失败: 图像文件不存在，请先完成 Step 2", None
        
        # 执行视频生成
        result = step4_main()
        
        # 检查输出视频
        video_dir = project_dir / "video"
        if video_dir.exists():
            video_files = list(video_dir.glob("*.mp4"))
            if video_files:
                # 获取最新的视频文件
                latest_video = max(video_files, key=os.path.getctime)
                success_msg = f"✅ Step 4 完成: 视频生成成功\n输出文件: {latest_video.name}"
                return success_msg, str(latest_video)
        
        return "✅ Step 4 完成: 视频生成完成", None
        
    except Exception as e:
        return f"❌ Step 4 失败: {str(e)}", None

def load_existing_videos():
    """加载现有的视频文件"""
    try:
        video_dir = project_dir / "video"
        
        if not video_dir.exists():
            return "❌ 视频目录不存在", None, []
        
        # 查找所有 .mp4 文件
        video_files = list(video_dir.glob("*.mp4"))
        
        if not video_files:
            return "❌ 未找到视频文件", None, []
        
        # 按修改时间排序，最新的在前
        video_files.sort(key=os.path.getctime, reverse=True)
        
        # 返回最新的视频文件用于预览
        latest_video = video_files[0]
        result_text = f"✅ 找到 {len(video_files)} 个视频文件\n"
        result_text += "现有文件（按时间排序）:\n"
        for i, file_path in enumerate(video_files):
            result_text += f"  {i+1}. {file_path.name}\n"
        
        return result_text, str(latest_video), [str(f) for f in video_files]
        
    except Exception as e:
        return f"❌ 加载失败: {str(e)}", None, []

def preview_video(video_files, selected_index):
    """预览选中的视频文件"""
    try:
        if video_files and 0 <= selected_index < len(video_files):
            return video_files[selected_index]
        return None
    except:
        return None

def check_prerequisites():
    """检查前置步骤是否完成"""
    status = []
    
    # 检查场景分割文件
    scenarios_file = project_dir / "scripts" / "场景分割.json"
    if scenarios_file.exists():
        with open(scenarios_file, 'r', encoding='utf-8') as f:
            scenarios = json.load(f)
        status.append(f"✅ 场景分割: {len(scenarios)} 个场景")
    else:
        status.append("❌ 场景分割: 文件不存在")
    
    # 检查图像文件
    image_dir = project_dir / "image"
    if image_dir.exists():
        image_files = list(image_dir.glob("output_*"))
        status.append(f"✅ 图像文件: {len(image_files)} 个")
    else:
        status.append("❌ 图像文件: 目录不存在")
    
    # 检查音频文件
    voice_dir = project_dir / "voice"
    if voice_dir.exists():
        audio_files = list(voice_dir.glob("*.wav"))
        status.append(f"✅ 音频文件: {len(audio_files)} 个")
    else:
        status.append("❌ 音频文件: 目录不存在")
    
    return "\n".join(status)

def create_interface():
    """创建 Step 4 的 Gradio 界面"""
    with gr.TabItem("🎬 Step 4: 视频输出"):
        gr.Markdown("### 合成最终视频")
        
        with gr.Row():
            with gr.Column():
                # 检查前置条件
                gr.Markdown("#### 📋 前置条件检查")
                step4_prerequisites = gr.Textbox(
                    label="前置步骤状态",
                    value=check_prerequisites(),
                    lines=4,
                    interactive=False
                )
                step4_check_btn = gr.Button("🔄 刷新状态", variant="secondary")
                
                gr.Markdown("#### ⚙️ 视频设置")
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
                    choices=[
                        ("淡入淡出", "fade"),
                        ("滑动切换", "slide"), 
                        ("旋转", "rotate"),
                        ("滚动", "scroll"),
                        ("水平翻转", "flip_horizontal"),
                        ("垂直翻转", "flip_vertical")
                    ],
                    value="fade"
                )
                
                with gr.Row():
                    step4_btn = gr.Button("🎬 生成视频", variant="primary")
                    step4_load_btn = gr.Button("📁 加载现有视频", variant="secondary")
            
            with gr.Column():
                step4_output = gr.Textbox(label="执行结果", lines=8)
                
                # 视频预览区域
                gr.Markdown("### 🎬 视频预览")
                step4_video_preview = gr.Video(
                    label="视频预览",
                    interactive=False
                )
                
                # 视频文件选择
                step4_video_selector = gr.Slider(
                    label="选择视频文件（1开始）",
                    minimum=1,
                    maximum=10,
                    value=1,
                    step=1,
                    visible=False
                )
                
                # 视频文件信息显示
                with gr.Row():
                    step4_current_file = gr.Textbox(
                        label="当前文件",
                        interactive=False,
                        visible=False
                    )
        
        # 隐藏的状态变量用于存储视频文件列表
        step4_video_files = gr.State([])
        
        # 刷新状态按钮的回调
        step4_check_btn.click(
            fn=check_prerequisites,
            inputs=[],
            outputs=[step4_prerequisites]
        )
        
        # 生成视频按钮的回调
        step4_btn.click(
            fn=run_step4,
            inputs=[step4_fps, step4_enlarge, step4_enable_effect, step4_effect_type],
            outputs=[step4_output, step4_video_preview]
        ).then(
            fn=load_existing_videos,
            inputs=[],
            outputs=[step4_output, step4_video_preview, step4_video_files]
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
            inputs=[step4_video_files],
            outputs=[step4_video_selector, step4_current_file]
        )
        
        # 加载现有视频按钮的回调
        step4_load_btn.click(
            fn=load_existing_videos,
            inputs=[],
            outputs=[step4_output, step4_video_preview, step4_video_files]
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
            inputs=[step4_video_files],
            outputs=[step4_video_selector, step4_current_file]
        )
        
        # 视频选择器的回调
        step4_video_selector.change(
            fn=lambda files, idx: [
                preview_video(files, int(idx)-1) if files else None,
                os.path.basename(files[int(idx)-1]) if files and 0 <= int(idx)-1 < len(files) else ""
            ],
            inputs=[step4_video_files, step4_video_selector],
            outputs=[step4_video_preview, step4_current_file]
        )

def run_step4_for_all(fps=30, enlarge_background=True, enable_effect=True, effect_type="fade"):
    """供一键生成调用的简化版本"""
    result, video_path = run_step4(fps, enlarge_background, enable_effect, effect_type)
    return result
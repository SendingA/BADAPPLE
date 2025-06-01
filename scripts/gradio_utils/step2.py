import gradio as gr
import os
import json
from pathlib import Path
import sys

# 添加项目路径
project_dir = Path(__file__).parent.parent.parent
scripts_dir = project_dir / "scripts"
sys.path.append(str(scripts_dir))

from step2_txt_to_image_webui import (
    run_webui_program, 
    get_generated_images, 
    regenerate_images,
    set_server_urls,
    get_available_servers,
    SERVER_URLS
)

def test_servers(server_urls_text):
    """测试服务器连接状态"""
    if not server_urls_text.strip():
        return "请输入服务器地址"
    
    urls = [url.strip() for url in server_urls_text.split('\n') if url.strip()]
    set_server_urls(urls)
    
    available = get_available_servers()
    
    result = f"测试完成！\n总共: {len(urls)} 个服务器\n可用: {len(available)} 个服务器\n\n"
    
    for url in urls:
        status = "✅ 可用" if url in available else "❌ 不可用"
        result += f"{url} - {status}\n"
    
    return result

def run_step2(server_urls_text, max_workers, width, height, steps, sampler, scheduler, 
              cfg_scale, seed, enable_hr, hr_scale, hr_upscaler, denoising_strength, 
              more_details, negative_prompt, control_image):
    """执行 Step 2: 文本转图像（多服务器版本）"""
    try:
        # 设置服务器列表
        if server_urls_text.strip():
            urls = [url.strip() for url in server_urls_text.split('\n') if url.strip()]
            set_server_urls(urls)
        
        # 更新配置
        config_path = project_dir / "config.json"
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        # 更新图像生成参数
        extra_params = {
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
        }
        
        config.update(extra_params)
        
        if more_details:
            config["more_details"] = more_details
        if negative_prompt:
            config["negative_prompt"] = negative_prompt
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 处理控制图
        control_path = None
        if control_image:
            control_path = project_dir / "control_image.png"
            control_image.save(control_path)
            control_path = str(control_path)
        
        # 执行生成（并行）
        run_webui_program(
            extra_params=extra_params,
            control_image=control_path,
            max_workers=max_workers
        )
        
        # 刷新图片展示
        return "✅ Step 2 完成：图像生成完成", update_image_gallery()
        
    except Exception as e:
        return f"❌ Step 2 失败: {str(e)}", gr.update()

def update_image_gallery():
    """更新图片画廊"""
    grouped_images = get_generated_images()
    
    if not grouped_images:
        return gr.update(value=[])
    
    # 构建画廊数据
    gallery_data = []
    for group in grouped_images:
        for img_info in group['images']:
            gallery_data.append((
                img_info['path'],
                f"场景: {group['scenario'][:30]}...\n图片: {img_info['name']}\n索引: {img_info['index']}"
            ))
    
    return gr.update(value=gallery_data)

def get_scenario_display():
    """获取场景展示数据"""
    grouped_images = get_generated_images()
    
    if not grouped_images:
        return "暂无生成的图片"
    
    display_html = ""
    for i, group in enumerate(grouped_images):
        display_html += f"""
        <div style="border: 1px solid #ddd; margin: 10px; padding: 10px; border-radius: 5px;">
            <h4>场景 {i+1}: {group['scenario']}</h4>
            <p style="color: #666; font-size: 14px;">{group['content'][:100]}...</p>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">
        """
        
        for img_info in group['images']:
            display_html += f"""
                <div style="text-align: center;">
                    <img src="file://{img_info['path']}" style="width: 120px; height: 120px; object-fit: cover; border-radius: 3px;">
                    <p style="font-size: 12px; margin: 5px 0;">{img_info['name']}</p>
                    <p style="font-size: 10px; color: #999;">索引: {img_info['index']}</p>
                </div>
            """
        
        display_html += """
            </div>
        </div>
        """
    
    return display_html

def handle_regenerate(selected_indices_str):
    """处理重绘请求"""
    if not selected_indices_str.strip():
        return "请输入要重绘的图片索引", gr.update()
    
    try:
        # 解析索引
        indices = [int(x.strip()) for x in selected_indices_str.split(',') if x.strip().isdigit()]
        if not indices:
            return "请输入有效的图片索引（用逗号分隔）", gr.update()
        
        # 执行重绘
        result = regenerate_images(indices)
        
        # 刷新展示
        return result, update_image_gallery()
        
    except Exception as e:
        return f"重绘失败: {str(e)}", gr.update()

def create_interface():
    """创建 Step 2 界面"""
    with gr.TabItem("🎨 Step 2: 图像生成"):
        gr.Markdown("### 根据提示词生成场景图像（支持多服务器并行）")
        
        with gr.Row():
            # 左侧：生成参数
            with gr.Column(scale=1):
                gr.Markdown("#### 服务器配置")
                
                with gr.Group():
                    step2_server_urls = gr.Textbox(
                        label="WebUI 服务器地址（每行一个）",
                        value="\n".join(SERVER_URLS),
                        placeholder="http://localhost:7860\nhttp://192.168.1.100:7861\nhttp://server3:7862",
                        lines=4,
                        info="支持多个服务器并行生成，每行输入一个地址"
                    )
                    
                    test_servers_btn = gr.Button("🔍 测试连接", variant="primary")
                    step2_max_workers = gr.Number(
                        label="最大并行数",
                        value=len(SERVER_URLS),
                        info="建议不超过服务器数量"
                    )
                    
                    server_status = gr.Textbox(
                        label="服务器状态",
                        lines=6,
                        interactive=False
                    )
                
                gr.Markdown("#### 生成参数")
                
                # 基础参数
                with gr.Group():
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
                
                # 高分辨率修复参数
                with gr.Group():
                    step2_enable_hr = gr.Checkbox(label="启用高分辨率修复", value=False)
                    step2_hr_scale = gr.Slider(label="放大倍数", minimum=1, maximum=4, value=2, step=0.1)
                    step2_hr_upscaler = gr.Dropdown(
                        label="放大算法",
                        choices=["Latent", "ESRGAN_4x", "R-ESRGAN 4x+"],
                        value="Latent"
                    )
                    step2_denoising = gr.Slider(label="去噪强度", minimum=0, maximum=1, value=0.7, step=0.05)
                
                # 额外参数
                with gr.Group():
                    step2_more_details = gr.Textbox(label="额外正面提示（可选）")
                    step2_negative = gr.Textbox(label="负面提示（可选）")
                    step2_control_image = gr.Image(label="控制图（可选）", type="pil")

                
                step2_btn = gr.Button("🎨 开始并行生成", variant="primary", size="lg")
                step2_output = gr.Textbox(label="执行结果", lines=3)
            
            # 右侧：图片展示和重绘
            with gr.Column(scale=2):
                gr.Markdown("#### 生成的图片")
                
                refresh_btn = gr.Button("🔄 刷新图片展示", variant="secondary")
                
                # 图片画廊
                image_gallery = gr.Gallery(
                    label="生成的图片",
                    show_label=True,
                    elem_id="step2_gallery",
                    columns=4,
                    rows=3,
                    object_fit="cover",
                    height=400
                )
                
                # 场景分组展示
                with gr.Accordion("📋 按场景查看", open=False):
                    scenario_display = gr.HTML(label="场景分组")
                
                # 重绘功能
                gr.Markdown("#### 重绘功能")
                regenerate_indices = gr.Textbox(
                    label="要重绘的图片索引",
                    placeholder="例如: 1,3,5,7 (用逗号分隔)",
                    info="输入要重绘的图片索引号，可在上方图片展示中查看"
                )
                
                with gr.Row():
                    regenerate_btn = gr.Button("🎨 重绘选中图片", variant="primary")
                    clear_indices_btn = gr.Button("🗑️ 清空选择", variant="secondary")
                
                regenerate_output = gr.Textbox(label="重绘结果", lines=2)
        
        # 事件绑定
        test_servers_btn.click(
            fn=test_servers,
            inputs=step2_server_urls,
            outputs=server_status
        )
        
        step2_btn.click(
            fn=run_step2,
            inputs=[
                step2_server_urls, step2_max_workers, step2_width, step2_height, step2_steps, 
                step2_sampler, step2_scheduler, step2_cfg, step2_seed, step2_enable_hr, 
                step2_hr_scale, step2_hr_upscaler, step2_denoising, step2_more_details, 
                step2_negative, step2_control_image
            ],
            outputs=[step2_output, image_gallery]
        )
        
        refresh_btn.click(
            fn=update_image_gallery,
            outputs=image_gallery
        )
        
        refresh_btn.click(
            fn=get_scenario_display,
            outputs=scenario_display
        )
        
        regenerate_btn.click(
            fn=handle_regenerate,
            inputs=regenerate_indices,
            outputs=[regenerate_output, image_gallery]
        )
        
        clear_indices_btn.click(
            fn=lambda: "",
            outputs=regenerate_indices
        )
        

    return {
        'run_step2': run_step2,
        'update_gallery': update_image_gallery,
        'regenerate': handle_regenerate,
        'test_servers': test_servers
    }
import os
import gc
import random
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageFilter
from moviepy.editor import (
    ImageSequenceClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    VideoFileClip,
    vfx
)
import json
from datetime import datetime
import chardet
from tqdm import tqdm
import numpy as np

def get_config():
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')

    with open(config_file, 'rb') as f:
        encoding_result = chardet.detect(raw_data := f.read())
        encoding = encoding_result['encoding']

    return json.loads(raw_data.decode(encoding))

def transform_image(img, t, x_speed, y_speed, move_on_x, move_positive):
    original_size = img.size

    crop_width = img.width * 0.8
    crop_height = img.height * 0.8
    if move_on_x:
        left = min(x_speed * t, img.width - crop_width) if move_positive else max(img.width - crop_width - x_speed * t, 0)
        upper = (img.height - crop_height) / 2
    else:
        upper = min(y_speed * t, img.height - crop_height) if move_positive else max(img.height - crop_height - y_speed * t, 0)
        left = (img.width - crop_width) / 2

    right = left + crop_width
    lower = upper + crop_height

    cropped_img = img.crop((left, upper, right, lower))
    
    return cropped_img.resize(original_size)

def main():
    """主函数：生成视频"""
    try:
        print("BADAPPLE - 开始生成视频")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)

        config = get_config()

        image_dir = os.path.join(parent_dir, 'image')
        voice_dir = os.path.join(parent_dir, 'voice')
        video_dir = os.path.join(parent_dir, 'video')
        temp_dir = os.path.join(parent_dir, 'temp')
        scripts_dir = os.path.join(parent_dir, 'scripts')

        # 确保输出目录存在
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        # 检查场景分割文件是否存在
        scenarios_file = os.path.join(scripts_dir, '场景分割.json')
        if not os.path.exists(scenarios_file):
            raise FileNotFoundError("场景分割文件不存在，请先完成 Step 1")

        with open(scenarios_file, 'r', encoding='utf-8') as f:
            scenario_info = list(json.load(f).values())

        total_files = len(scenario_info)
        if total_files == 0:
            raise ValueError("场景分割文件为空")

        fps = config.get('fps', 30)
        enlarge_background = config.get('enlarge_background', True)
        enable_effect = config.get('enable_effect', True)
        effect_type_config = config.get('effect_type', 'fade')

        extensions = ['.png', '.jpg', '.jpeg']
        
        print(f"总共需要处理 {total_files} 个场景")

        for i in tqdm(range(total_files), ncols=None, desc="正在生成视频"):
            im_indices = scenario_info[i]['子图索引']
            audio_filename = os.path.join(voice_dir, f'output_{i}')
            temp_filename = os.path.join(temp_dir, f'output_{i}.mp4')

            # 检查音频文件是否存在
            if not os.path.exists(audio_filename + '.wav'):
                print(f"警告: 音频文件 {audio_filename}.wav 不存在，跳过场景 {i}")
                continue

            audio = AudioFileClip(audio_filename + '.wav')

            segment_duration = audio.duration / len(im_indices)
            segment_frames = int(segment_duration * fps)
            all_segments = []

            for idx in im_indices:
                img_path = None
                for ext in extensions:
                    potential_path = os.path.join(image_dir, f'output_{idx+1}{ext}')
                    if os.path.exists(potential_path):
                        img_path = potential_path
                        break

                if img_path is None:
                    print(f"警告: 图像 output_{idx+1} 未找到，跳过。")
                    continue

                im = Image.open(img_path)
                
                # 随机选择运动方向
                movement_type = random.choice([0, 1])

                if movement_type == 0:
                    x_speed = (im.width - im.width * 0.8) / segment_duration
                    y_speed = 0
                    move_on_x = True
                elif movement_type == 1:
                    x_speed = 0
                    y_speed = (im.height - im.height * 0.8) / segment_duration
                    move_on_x = False
                
                move_positive = random.choice([True, False])
                
                frames_foreground = [
                    np.array(transform_image(im, t / fps, x_speed, y_speed, move_on_x, move_positive)) 
                    for t in range(segment_frames)
                ]
                img_foreground = ImageSequenceClip(frames_foreground, fps=fps)

                img_blur = im.filter(ImageFilter.GaussianBlur(radius=30))
                if enlarge_background:
                    img_blur = img_blur.resize(
                        (int(im.width * 1.1), int(im.height * 1.1)), Image.Resampling.LANCZOS)
                frames_background = [np.array(img_blur)] * segment_frames
                img_background = ImageSequenceClip(frames_background, fps=fps)

                segment_clip = CompositeVideoClip(
                    [img_background.set_position("center"), img_foreground.set_position("center")], 
                    size=img_blur.size
                )

                # 应用特效（如果启用）
                if enable_effect:
                    segment_clip = {
                        'fade': segment_clip.fadein(1).fadeout(1),
                        'slide': segment_clip.crossfadein(1).crossfadeout(1),
                        'rotate': segment_clip.rotate(lambda t: 360*t/10),
                        'scroll': segment_clip.fx(vfx.scroll, y_speed=50),
                        'flip_horizontal': segment_clip.fx(vfx.mirror_x),
                        'flip_vertical': segment_clip.fx(vfx.mirror_y)
                    }.get(effect_type_config, segment_clip)
                
                all_segments.append(segment_clip)

            if all_segments:  # 只有当有有效片段时才生成视频
                final_clip = concatenate_videoclips(all_segments, method="compose").set_audio(audio)
                final_clip.write_videofile(temp_filename, verbose=False, logger=None)
                final_clip.close()  # 释放资源
                audio.close()
            
            gc.collect()

        # 合并所有临时视频文件
        print("正在合并所有视频片段...")
        temp_filenames = []
        for i in range(total_files):
            temp_file = os.path.join(temp_dir, f'output_{i}.mp4')
            if os.path.exists(temp_file):
                temp_filenames.append(temp_file)

        if not temp_filenames:
            raise RuntimeError("没有生成任何视频片段")

        temp_filenames.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
        
        video_clips = [VideoFileClip(filename) for filename in temp_filenames]
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        output_filename = os.path.join(video_dir, f'output_{datetime.now().strftime("%Y%m%d%H%M%S")}.mp4')
        final_video.write_videofile(output_filename, verbose=False, logger=None)
        
        # 清理资源
        for clip in video_clips:
            clip.close()
        final_video.close()
        
        print(f"✅ 视频生成完成: {output_filename}")
        return output_filename

    except Exception as e:
        print(f"❌ 视频生成失败: {str(e)}")
        raise e

if __name__ == "__main__":
    main()

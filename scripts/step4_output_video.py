import os
import gc
import random
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from moviepy.editor import (
    ImageSequenceClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    VideoFileClip,
    vfx,
    TextClip  # 添加 TextClip 导入
)
import json
from datetime import datetime
import chardet
import concurrent.futures
from tqdm import tqdm
import numpy as np
import textwrap
import re

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


def create_subtitle_image(text, width, height, fontsize=36):
    """创建简洁的字幕图像"""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        # 尝试使用支持中文的字体
        font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", fontsize)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", fontsize)
        except:
            font = ImageFont.load_default()
    
    if not text.strip():
        return np.array(img)
    
    # 获取文本尺寸
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 确保字幕在屏幕范围内
    margin = 20
    if text_width > width - 2 * margin:
        # 如果文本太宽，缩小字体
        fontsize = int(fontsize * (width - 2 * margin) / text_width)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", fontsize)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    
    # 计算居中位置（靠近底部）
    x = (width - text_width) // 2
    y = height - text_height - 80  # 距离底部80像素
    
    # 确保不会超出边界
    x = max(margin, min(x, width - text_width - margin))
    y = max(margin, min(y, height - text_height - margin))
    
    # 绘制半透明背景
    bg_padding = 10
    bg_left = x - bg_padding
    bg_top = y - bg_padding
    bg_right = x + text_width + bg_padding
    bg_bottom = y + text_height + bg_padding
    draw.rectangle([bg_left, bg_top, bg_right, bg_bottom], fill=(0, 0, 0, 128))
    
    # 绘制文本描边
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
    
    # 绘制主文本
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    
    return np.array(img)

def load_audio_timing_info(voice_dir):
    """加载音频时长信息"""
    timing_file = os.path.join(voice_dir, "audio_timing.json")
    sentence_mapping_file = os.path.join(voice_dir, "sentence_mapping.json")
    
    timing_info = {}
    sentence_mapping = {}
    
    if os.path.exists(timing_file):
        with open(timing_file, 'r', encoding='utf-8') as f:
            timing_info = json.load(f)
    
    if os.path.exists(sentence_mapping_file):
        with open(sentence_mapping_file, 'r', encoding='utf-8') as f:
            sentence_mapping_list = json.load(f)
            # 转换为以场景索引为键的字典
            for item in sentence_mapping_list:
                sentence_mapping[item["scenario_index"]] = item
    
    return timing_info, sentence_mapping

def process_subtitle_ending(subtitle):
    """处理字幕末尾，移除结束标点符号"""
    if not subtitle:
        return subtitle
    
    # 定义结束标点符号
    ending_punctuation = ['。', '！', '？', '.', '!', '?', '；', ';', '，', ',']
    
    # 如果最后一个字符是结束标点符号，则移除
    while subtitle and subtitle[-1] in ending_punctuation:
        subtitle = subtitle[:-1]
    
    return subtitle.strip()

def create_subtitles_from_audio_timing(scenario_index, timing_info, sentence_mapping, max_chars_per_subtitle=20):
    """根据音频时长信息创建字幕，平均分配显示时间"""
    audio_key = f"output_{scenario_index}"
    
    if audio_key not in timing_info or scenario_index not in sentence_mapping:
        return []
    
    sentence_durations = timing_info[audio_key].get("sentence_durations", [])
    processed_sentences = sentence_mapping[scenario_index].get("processed_sentences", [])
    total_duration = timing_info[audio_key].get("total_duration", 0)
    
    if not sentence_durations or not processed_sentences or total_duration <= 0:
        return []
    
    # 将所有句子合并成一个完整文本
    full_text = ''.join(processed_sentences)
    
    # 智能分割文本，考虑双引号的情况
    def smart_split_text(text):
        """智能分割文本，保护双引号内的内容"""
        parts = []
        current_part = ""
        in_quotes = False
        quote_chars = ['“', '”']  # 各种引号类型
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # 检查是否遇到引号
            if char in quote_chars and not in_quotes:
                in_quotes = True
                current_part += char
            elif char in quote_chars and in_quotes:
                in_quotes = False
                current_part += char
            # 如果在引号内，直接添加字符
            elif in_quotes:
                current_part += char
            # 如果不在引号内，检查分割标点
            elif char in ['，', ',', '。', '！', '？', '；', ';']:
                current_part += char
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
            
            i += 1
        
        # 添加最后一部分
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    text_parts = smart_split_text(full_text)
    
    # 智能合并：区分结束标点符号和中间标点符号
    merged_subtitles = []
    current_subtitle = ""
    
    # 定义结束标点符号和中间标点符号
    ending_punctuation = ['。', '！', '？', '.', '!', '?']
    middle_punctuation = ['，', ',', '；', ';']
    
    for part in text_parts:
        # 检查当前字幕是否以结束标点符号结尾
        current_ends_with_ending = current_subtitle and current_subtitle[-1] in ending_punctuation
        
        # 如果当前字幕以结束标点符号结尾，不能合并
        if current_ends_with_ending:
            # 保存当前字幕
            processed_subtitle = process_subtitle_ending(current_subtitle)
            if processed_subtitle:  # 确保字幕不为空
                merged_subtitles.append(processed_subtitle)
            current_subtitle = part
        # 如果当前字幕加上新部分不超过长度限制，且当前字幕不以结束标点符号结尾
        elif len(current_subtitle + part) <= max_chars_per_subtitle:
            current_subtitle += part
        else:
            # 保存当前字幕（如果不为空）
            if current_subtitle:
                processed_subtitle = process_subtitle_ending(current_subtitle)
                if processed_subtitle:  # 确保字幕不为空
                    merged_subtitles.append(processed_subtitle)
                current_subtitle = ""
            
            # 如果单个部分太长，需要强制拆分
            if len(part) > max_chars_per_subtitle:
                for i in range(0, len(part), max_chars_per_subtitle):
                    chunk = part[i:i + max_chars_per_subtitle]
                    processed_chunk = process_subtitle_ending(chunk)
                    if processed_chunk:  # 确保字幕不为空
                        merged_subtitles.append(processed_chunk)
            else:
                current_subtitle = part
    
    # 添加最后的字幕
    if current_subtitle:
        processed_subtitle = process_subtitle_ending(current_subtitle)
        if processed_subtitle:  # 确保字幕不为空
            merged_subtitles.append(processed_subtitle)
    
    # 如果没有生成任何字幕，返回空
    if not merged_subtitles:
        return []
    
    # 平均分配时间：总时长除以字幕数量
    subtitle_duration = total_duration / len(merged_subtitles)
    
    # 创建字幕列表，每个字幕显示时间相等
    subtitles = []
    for i, subtitle_text in enumerate(merged_subtitles):
        start_time = i * subtitle_duration
        end_time = (i + 1) * subtitle_duration
        # 确保最后一个字幕不超过总时长
        if i == len(merged_subtitles) - 1:
            end_time = total_duration
        subtitles.append((subtitle_text, start_time, end_time))
    
    return subtitles

def split_text_by_time(text, total_duration, subtitle_duration=2.5, max_chars_per_subtitle=20):
    """根据时间切割文本为短字幕，平均分配时间"""
    if not text:
        return []
    
    # 移除多余的空格和换行
    text = ' '.join(text.split())
    
    # 如果文本很短，只用一个字幕
    if len(text) <= max_chars_per_subtitle:
        processed_text = process_subtitle_ending(text)
        return [(processed_text, 0, total_duration)]
    
    # 智能分割文本，考虑双引号的情况
    def smart_split_text(text):
        """智能分割文本，保护双引号内的内容"""
        parts = []
        current_part = ""
        in_quotes = False
        quote_chars = ['"', '"', '"', "'", "'"]  # 各种引号类型
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # 检查是否遇到引号
            if char in quote_chars and not in_quotes:
                in_quotes = True
                current_part += char
            elif char in quote_chars and in_quotes:
                in_quotes = False
                current_part += char
            # 如果在引号内，直接添加字符
            elif in_quotes:
                current_part += char
            # 如果不在引号内，检查分割标点
            elif char in ['，', ',', '。', '！', '？', '；', ';']:
                current_part += char
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
            
            i += 1
        
        # 添加最后一部分
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    text_parts = smart_split_text(text)
    
    # 如果没有分割出部分，回退到原始文本
    if not text_parts:
        text_parts = [text]
    
    # 智能合并：区分结束标点符号和中间标点符号
    merged_subtitles = []
    current_subtitle = ""
    
    # 定义结束标点符号和中间标点符号
    ending_punctuation = ['。', '！', '？', '.', '!', '?']
    middle_punctuation = ['，', ',', '；', ';']
    
    for part in text_parts:
        # 检查当前字幕是否以结束标点符号结尾
        current_ends_with_ending = current_subtitle and current_subtitle[-1] in ending_punctuation
        
        # 如果当前字幕以结束标点符号结尾，不能合并
        if current_ends_with_ending:
            # 保存当前字幕
            processed_subtitle = process_subtitle_ending(current_subtitle)
            if processed_subtitle:  # 确保字幕不为空
                merged_subtitles.append(processed_subtitle)
            current_subtitle = part
        # 如果当前字幕加上新部分不超过长度限制，且当前字幕不以结束标点符号结尾
        elif len(current_subtitle + part) <= max_chars_per_subtitle:
            current_subtitle += part
        else:
            # 保存当前字幕（如果不为空）
            if current_subtitle:
                processed_subtitle = process_subtitle_ending(current_subtitle)
                if processed_subtitle:  # 确保字幕不为空
                    merged_subtitles.append(processed_subtitle)
                current_subtitle = ""
            
            # 如果单个部分太长，需要强制拆分
            if len(part) > max_chars_per_subtitle:
                for i in range(0, len(part), max_chars_per_subtitle):
                    chunk = part[i:i + max_chars_per_subtitle]
                    processed_chunk = process_subtitle_ending(chunk)
                    if processed_chunk:  # 确保字幕不为空
                        merged_subtitles.append(processed_chunk)
            else:
                current_subtitle = part
    
    # 添加最后的字幕
    if current_subtitle:
        processed_subtitle = process_subtitle_ending(current_subtitle)
        if processed_subtitle:  # 确保字幕不为空
            merged_subtitles.append(processed_subtitle)
    
    # 如果没有生成任何字幕，至少添加一个
    if not merged_subtitles:
        processed_text = process_subtitle_ending(text[:max_chars_per_subtitle])
        merged_subtitles = [processed_text]
    
    # 平均分配时间：总时长除以字幕数量
    subtitle_duration_avg = total_duration / len(merged_subtitles)
    
    # 创建字幕列表，每个字幕显示时间相等
    subtitles = []
    for i, subtitle_text in enumerate(merged_subtitles):
        start_time = i * subtitle_duration_avg
        end_time = (i + 1) * subtitle_duration_avg
        # 确保最后一个字幕不超过总时长
        if i == len(merged_subtitles) - 1:
            end_time = total_duration
        subtitles.append((subtitle_text, start_time, end_time))
    
    return subtitles

def main():

    print("BADAPPLE")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

    config = get_config()

    image_dir = os.path.join(parent_dir, 'image')
    voice_dir = os.path.join(parent_dir, 'voice')
    video_dir = os.path.join(parent_dir, 'video')
    temp_dir = os.path.join(parent_dir, 'temp')
    scripts_dir = os.path.join(parent_dir, 'scripts')

    with open(os.path.join(scripts_dir, '场景分割.json'), 'r', encoding='utf-8') as f:
        scenario_info = list(json.load(f).values())
    os.makedirs(temp_dir, exist_ok=True)

    total_files = len(scenario_info)
    fps = config['fps']
    enlarge_background = config['enlarge_background']
    enable_effect = config['enable_effect']
    effect_type = config['effect_type']

    extensions = ['.png', '.jpg', '.jpeg']
    # 加载音频时长信息
    timing_info, sentence_mapping = load_audio_timing_info(voice_dir)
    # 在主循环中修改字幕长度限制
    for i in tqdm(range(total_files), ncols=None, desc="正在生成视频"):
        im_indices = scenario_info[i]['子图索引']
        audio_filename = os.path.join(voice_dir, f'output_{i}')
        temp_filename = os.path.join(temp_dir, f'output_{i}.mp4')

        audio = AudioFileClip(audio_filename + '.wav')

        # 使用音频时长信息创建精确对齐的字幕（增加字幕长度）
        subtitle_list = create_subtitles_from_audio_timing(i, timing_info, sentence_mapping, max_chars_per_subtitle=23)

        # 如果没有获取到时长信息，回退到原方法（同样增加字幕长度）
        if not subtitle_list:
            subtitle_text = scenario_info[i].get('内容', '')
            subtitle_list = split_text_by_time(subtitle_text, audio.duration, subtitle_duration=2.5, max_chars_per_subtitle=23)

        segment_duration = audio.duration / len(im_indices)
        segment_frames = int(segment_duration * fps)
        all_segments = []

        for idx_num, idx in enumerate(im_indices):
            for ext in extensions:
                try:
                    img_path = os.path.join(image_dir, f'output_{idx+1}{ext}')
                    if os.path.exists(img_path):
                        break
                except FileNotFoundError:
                    print(f"图像 output_{idx} 未找到，跳过。")
                    continue

            im = Image.open(img_path)
            effect_type = random.choice([0, 1])

            if effect_type == 0:
                x_speed = (im.width - im.width * 0.8) / segment_duration
                y_speed = 0
                move_on_x = True
            elif effect_type == 1:
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

            # 为当前时间段添加相应的字幕
            segment_start_time = idx_num * segment_duration
            segment_end_time = (idx_num + 1) * segment_duration

            # 收集在当前时间段内的字幕
            current_subtitles = []
            for subtitle_text, start_time, end_time in subtitle_list:
                # 检查字幕时间是否与当前段重叠
                if not (end_time <= segment_start_time or start_time >= segment_end_time):
                    # 计算在当前段内的显示时间
                    display_start = max(0, start_time - segment_start_time)
                    display_end = min(segment_duration, end_time - segment_start_time)
                    current_subtitles.append((subtitle_text, display_start, display_end))

            # 创建字幕图层
            if current_subtitles:
                subtitle_clips = []
                for subtitle_text, display_start, display_end in current_subtitles:
                    subtitle_img = create_subtitle_image(subtitle_text, img_blur.size[0], img_blur.size[1])

                    # 计算需要显示的帧数
                    start_frame = int(display_start * fps)
                    end_frame = int(display_end * fps)
                    subtitle_frames = [subtitle_img] * (end_frame - start_frame)

                    if subtitle_frames:
                        subtitle_clip = ImageSequenceClip(subtitle_frames, fps=fps)
                        subtitle_clip = subtitle_clip.set_start(display_start)
                        subtitle_clips.append(subtitle_clip)

                # 如果有字幕，添加到视频中
                if subtitle_clips:
                    segment_clip = CompositeVideoClip([segment_clip] + subtitle_clips)

            all_segments.append(segment_clip)

        final_clip = concatenate_videoclips(all_segments, method="compose").set_audio(audio)
        final_clip.write_videofile(temp_filename)
        gc.collect()

    temp_filenames = [os.path.join(temp_dir, f'output_{i}.mp4') for i in range(total_files)]
    temp_filenames.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
    final_video = concatenate_videoclips([VideoFileClip(filename) for filename in temp_filenames], method="compose")
    final_video.write_videofile(os.path.join(video_dir, f'output_{datetime.now().strftime("%Y%m%d%H%M%S")}.mp4'))
    
if __name__ == "__main__":
    main()
    print("🎉 视频生成完成！")

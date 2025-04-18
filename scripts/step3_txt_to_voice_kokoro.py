from kokoro import KModel, KPipeline
import numpy as np
import soundfile as sf
import torch
import tqdm
import os
import os
import openpyxl
import asyncio
import tqdm
import argparse
import json

class SpeechProvider:
    def __init__(self, gender, language):
        REPO_ID = 'hexgrad/Kokoro-82M-v1.1-zh'
        kororo_path = os.path.join(os.path.dirname(__file__), '..', 'voice', 'Kokoro-82M-v1.1-zh')
        config = kororo_path + '/config.json'
        model_pth = kororo_path + '/kokoro-v1_1-zh.pth'

        self.SAMPLE_RATE = 24000
        # How much silence to insert between paragraphs: 5000 is about 0.2 seconds
        self.N_ZEROS = 10000
        # VOICES = glob.glob(f"./voice/Kokoro-82M-v1.1-zh/voices/{GENDER}*.pt")
        self.VOICE = kororo_path + '/voices/zf_003.pt' if gender == 'zf' else kororo_path + '/voices/zm_031.pt'
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = KModel(repo_id=REPO_ID, config=config, model=model_pth).to(self.device).eval()
        self.en_pipeline = KPipeline(lang_code='a', repo_id=REPO_ID, model=False)
        self.zh_pipeline = KPipeline(lang_code='z', repo_id=REPO_ID, model=self.model, en_callable=self.en_callable)
        self.zh_pipeline.load_voice


    def en_callable(self,text):
        if text == 'Kokoro':
            return 'kˈOkəɹO'
        elif text == 'Sol':
            return 'sˈOl'
        return next(self.en_pipeline(text)).phonemes

    def speed_callable(self,len_ps):
        speed = 0.82
        if len_ps <= 100:
            speed = 1
        elif len_ps < 200:
            speed = 1 - (len_ps - 100) / 500
        return speed * 1.1

    def get_tts_audio(self, message):
        wavs = []
        for paragraph in tqdm.tqdm(message, desc="正在生成配音音频", unit="paragraphs"):
            for i, sentence in enumerate(paragraph):
                generator = self.zh_pipeline(sentence, voice=self.VOICE, speed=self.speed_callable)
                result = next(generator)
                wav = result.audio
                if i == 0 and wavs and self.N_ZEROS > 0:
                    wav = np.concatenate([np.zeros(self.N_ZEROS), wav])
                wavs.append(wav)

        return 'wav', wavs

def  convert_text_to_audio(tasks, language, output_path,gender):
    if not tasks:
        return False

    provider = SpeechProvider(gender,language)
    wav_format, wavs = provider.get_tts_audio(tasks)
    if wav_format != 'wav':
        raise ValueError("Unsupported audio format")
    if wavs is not None:
        for index, wav in enumerate(wavs):
            wav_file_path = os.path.join(output_path, f"output_{index}.wav")
            sf.write(f"{wav_file_path}", wav, provider.SAMPLE_RATE)
    return False

def process_text_files(input_file, output_dir, language, gender):
    print("BADAPPLE")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    scenarios = [item["内容"] for item in data.values()]
    tasks = []
    for scenario in scenarios:
        tasks.append((scenario,))
    convert_text_to_audio(tasks, language, output_dir, gender)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Text to Speech Converter')
    script_dir = os.path.dirname(os.path.realpath(__file__))

    default_input_file = os.path.join(script_dir, "..", "scripts", "场景分割.json")
    default_output_dir = os.path.join(script_dir, "..", "voice")


    parser.add_argument('--input_file', type=str, default=default_input_file, help='输入文本文件的路径')
    parser.add_argument('--output_dir', type=str, default=default_output_dir, help='输出目录的路径')
    parser.add_argument('--language', type=str, default="zh", help='文本的语言')
    parser.add_argument('--gender', type=str, default="zf", help='声音的性别')
    args = parser.parse_args()

    process_text_files(args.input_file, args.output_dir, args.language, args.gender)


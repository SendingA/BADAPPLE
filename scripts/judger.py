import base64
from openai import OpenAI


def image_2_base64_with_mime(image):
    image_base64 = base64.b64encode(image).decode("utf-8")
    image_base64_with_mime = f"data:image/jpeg;base64,{image_base64}"
    return image_base64_with_mime


class Judger:
    def __init__(
        self,
        api_key="sk-cLHG0jRuBeFDE49617b9T3BLBkFJe5b79d2bDefD4Db7b9fa",
        base_url="https://cn2us02.opapi.win/v1",
        examples=None,
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        
        self.examples = examples or self.default_examples()
            
        self.messages = [({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Hi, I am using Stable Diffusion to generate images. " + \
                        "I need you to judge whether the generated images match their prompts" + \
                        ", especially the content information. " + \
                        "For better understanding, here are 3 example cases. " + \
                        "Each case contains a prompt, a good image, and a bad image."
                },
            ]
        })]
        
        for example in self.examples:
            self.messages[0]["content"] += [
                {
                    "type": "text",
                    "text": example["prompt"]
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_2_base64_with_mime(example['good_image']),
                    }
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_2_base64_with_mime(example['bad_image']),
                    }
                },
            ]
        
        self.messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Now, I will give you a prompt and a images. " + \
                            "Please tell me if the images match the prompt. " + \
                            "YOUR ANSWER MUST BE 'Good' OR 'Bad' WITHOUT ANY OTHER DESCRIPTIONS!"
                    }
                ]
            }
        )
    
    def judge(self, prompt, image) -> bool:
        messages = self.messages + [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_2_base64_with_mime(image)
                        }
                    }
                ]
            }
        ]

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
        )
        
        res = response.choices[0].message.content.strip()
        print(f"Response: {res}")
        return res == "Good"
    
    def default_examples(self):
        examples = [
                {
                    "prompt": """middle aged king with dignified expression, splendid golden robe, gem encrusted crown, finely crafted sword, steady steps, (beautiful detailed eyes, beautiful detailed lips, extremely detailed face and beard, sharp focus), ultra detailed, realistic, photorealistic, masterpiece, best quality, vivid colors, HDR, studio lighting, dynamic pose, elegant atmosphere,
==BREAK==
(new queen in her forties), pale skin, deep brown curls, dark brown eyes, brocade gown black and red, gold thread embroidery on hem, emerald necklace and earrings, multiple rings, noble yet arrogant aura, (beautiful detailed eyes, beautiful detailed lips, long eyelashes, extremely detailed face), magnificent enchanted mirror, large silver mirror with black marble frame, intricate carvings, smooth surface shimmering with strange light, mysterious aura, held in hands, ultra fine painting, sharp focus, physically based rendering, professional, UHD, 4k resolution, perfect lighting, detailed background, royal hall setting, grand architecture, aesthetic composition""",
                    "good_image": None,
                    "bad_image": None,
                },
                {
                    "prompt": """massive silver mirror, black marble frame intricately carved with complex patterns, smooth as water, emitting unusual glow, revealing image of Snow White, gentle and dignified teenage girl around fifteen or sixteen years old, skin as white as snow, rosy cheeks, long black hair flowing down to waist, wearing light blue silk dress adorned with delicate lace, silver high heels on feet, beautiful detailed eyes, beautiful detailed lips, extremely detailed face, long eyelashes,
==BREAK==
(new Queen), woman in her forties, beautiful but somewhat stern appearance, pale skin, deep brown curly hair, dark brown eyes, dressed in black and red brocade gown embroidered with gold thread at hem, wearing emerald necklace and earrings, multiple rings on fingers, exuding air of nobility tinged with arrogance, (masterpiece:1.4, best quality), ultra-detailed, realistic, photorealistic, HDR, vivid colors, sharp focus, studio lighting, physically-based rendering, 8k resolution""",
                    "good_image": None,
                    "bad_image": None,
                },
                {
                    "prompt": """a woman, about forty years old, striking beauty with a stern expression, pale skin, deep brown curls, dark brown eyes blazing with fury, long brocade gown in black and red, golden thread embroidery on the hem, emerald necklace and earrings, fingers adorned with several rings, noble and arrogant aura, face contorted with rage, hands clenched into tight fists, beautiful detailed eyes, sharp facial features, long eyelashes, ultra-detailed, (realistic, photorealistic:1.37), studio lighting, vivid colors, HDR, UHD, sharp focus, professional, (masterpiece:1.2), best quality, 4k, 8k, highres""",
                    "good_image": None,
                    "bad_image": None,
                },
        ]
        
        for i in range(3):
            examples[i]['good_image'] = open(f"default_examples/example_{i}_g.png", "rb").read()
            examples[i]['bad_image'] = open(f"default_examples/example_{i}_b.png", "rb").read()
        
        return examples
        
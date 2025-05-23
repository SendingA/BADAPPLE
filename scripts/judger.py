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
        
        if not examples:
            examples = [
                {
                    "prompt": ,
                    "good_image": ,
                    "bad_image": ,
                },
                {
                    "prompt": ,
                    "good_image": ,
                    "bad_image": ,
                },
                {
                    "prompt": ,
                    "good_image": ,
                    "bad_image": ,
                },
            ]
            
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
            self.messages[0]["content"].append(
                {
                    "type": "text",
                    "text": example["prompt"]
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{example['good_image']}"
                    }
                }
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{example['bad_image']}"
                    }
                }
            )
        
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
        try:
            pass
        except Exception as e:
            print("Error:", e)
            return False

        return res == "Good"

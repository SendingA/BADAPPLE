from judger import Judger

if __name__ == "__main__":
    judger = Judger()
    prompt = "middle aged warrior, robust physique, short hair, dark skin, iron gray armor, sharp long sword, heavy leather boots, butchering a pig, removing heart and tongue, placing into a container, stern loyal expression, walking resolutely toward the palace, determined figure growing smaller in distance, (beautiful detailed eyes, beautiful detailed face, strong jawline, long eyelashes), ancient medieval setting, stone paved ground, dimly lit by torches, ultra detailed, (best quality,4k,8k,highres,masterpiece:1.2), realistic photorealistic, vivid colors, sharp focus, HDR lighting, professional composition, dynamic scene, dramatic atmosphere, physically based rendering"
    image = open(f"default_examples/trial.png", "rb").read()
    result = judger.judge(prompt, image)
    print(result)
    
    prompt = """middle aged king with dignified expression, splendid golden robe, gem encrusted crown, finely crafted sword, steady steps, (beautiful detailed eyes, beautiful detailed lips, extremely detailed face and beard, sharp focus), ultra detailed, realistic, photorealistic, masterpiece, best quality, vivid colors, HDR, studio lighting, dynamic pose, elegant atmosphere,
==BREAK==
(new queen in her forties), pale skin, deep brown curls, dark brown eyes, brocade gown black and red, gold thread embroidery on hem, emerald necklace and earrings, multiple rings, noble yet arrogant aura, (beautiful detailed eyes, beautiful detailed lips, long eyelashes, extremely detailed face), magnificent enchanted mirror, large silver mirror with black marble frame, intricate carvings, smooth surface shimmering with strange light, mysterious aura, held in hands, ultra fine painting, sharp focus, physically based rendering, professional, UHD, 4k resolution, perfect lighting, detailed background, royal hall setting, grand architecture, aesthetic composition""",
    image = open(f"default_examples/example_0_g.png", "rb").read()
    result = judger.judge(prompt, image)
    print(result)

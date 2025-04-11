pip install -U torch torchvision torchaudio torchmetrics

modelscope download \
    --model openai-mirror/clip-vit-base-patch16 \
    --local_dir .cache/openai/clip-vit-base-patch16

#!/usr/bin/env python3
"""
AnamnezAI - Gemma 4 Fine-Tuning Kurulum Scripti
RTX 5070 Ti (16GB VRAM) icin optimize edilmis
"""
import subprocess, sys, os
def run(cmd):
    print(f">> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"HATA: {result.stderr[:300]}")
        return False
    print(result.stdout[:200] if result.stdout else "OK")
    return True
print("=" * 60)
print("AnamnezAI - Gemma 4 Fine-Tuning Kurulumu")
print("RTX 5070 Ti (16GB VRAM) icin optimize")
print("=" * 60)
# CUDA kontrolu
import subprocess
nvidia_check = subprocess.run("nvidia-smi", shell=True, capture_output=True, text=True)
if nvidia_check.returncode == 0:
    lines = nvidia_check.stdout.split('\n')
    for line in lines[:10]:
        if line.strip():
            print(line)
else:
    print("UYARI: nvidia-smi bulunamadi. CUDA kurulu mu?")
# PyTorch CUDA versiyonunu belirle
print("\nPyTorch CUDA kurulumu...")
run(f"{sys.executable} -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
# Unsloth
print("\nUnsloth kurulumu...")
run(f"{sys.executable} -m pip install unsloth")
# Diger
print("\nDiger bagimliliklar...")
run(f"{sys.executable} -m pip install datasets transformers>=4.46.0 trl>=0.9.0 peft>=0.13.0 accelerate>=0.34.0 bitsandbytes>=0.44.0 sentencepiece huggingface_hub safetensors einops")
# Test
print("\nKurulum testi...")
test_code = """
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    gb = torch.cuda.get_device_properties(0).total_memory/1e9
    print(f'VRAM: {gb:.1f} GB')
try:
    import unsloth
    print('Unsloth: OK')
except:
    print('Unsloth: BASARISIZ')
try:
    from datasets import load_dataset
    print('datasets: OK')
except:
    print('datasets: BASARISIZ')
"""
run(f'{sys.executable} -c "{test_code}"')
print("\n" + "=" * 60)
print("Kurulum tamamlandi!")
print("Sonraki adim: train_gemma4_medical.ipynb dosyasini ac")
print("  jupyter notebook notebooks/train_gemma4_medical.ipynb")
print("=" * 60)

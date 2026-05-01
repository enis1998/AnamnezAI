# AnamnezAI - Gemma 4 Fine-Tuning Rehberi
## RTX 5070 Ti ile Adim Adim Egitim
---
## Gereksinimler
| Gereksinim | Detay |
|-----------|-------|
| GPU | RTX 5070 Ti (16GB VRAM) |
| RAM | 32GB+ onerilir |
| Disk | 50GB serbest alan |
| OS | Windows 11 / Ubuntu 22.04 |
| Python | 3.11+ |
| CUDA | 12.4+ |
---
## Adim 1: Kurulum
Egitim yapilacak bilgisayarda:
`ash
git clone https://github.com/enis1998/AnamnezAI.git
cd AnamnezAI/mediscreen/notebooks
python setup_training_env.py
`
---
## Adim 2: HuggingFace Token (Gemma 4 erisimi icin)
Gemma 4 modeli icin kabul formu gerekmektedir:
1. https://huggingface.co/google/gemma-4-4b-it adresine git
2. Lisans anlasmasi kabul et
3. HuggingFace API token olustur: https://huggingface.co/settings/tokens
4. Notebook'taki token satirini guncelle:
   token='hf_xxxxxxxxxxxxx'
---
## Adim 3: Egitimi Baslat
`ash
jupyter notebook train_gemma4_medical.ipynb
`
Veya dogrudan Python ile:
`ash
python -c "import nbformat; exec(open('train_gemma4_medical.ipynb').read())"
`
### Tahmini Sureler (RTX 5070 Ti)
| Veri Seti Boyutu | Epoch | Sure |
|-----------------|-------|------|
| 40K ornek | 2 | ~2-3 saat |
| 80K ornek | 2 | ~4-6 saat |
| 160K ornek | 2 | ~8-12 saat |
---
## Adim 4: GGUF Donusumu
Notebook icinde otomatik yapilir. Manuel olarak:
`ash
# GGUF dosyasi: gemma4-anamnez-gguf/gemma4-anamnez-q4_k_m.gguf
# Boyut: ~3.5GB (q4_k_m kalitesi)
`
---
## Adim 5: Ollama'ya Import
Egitim tamamlandiktan sonra modeli Ollama'ya ekle:
### Modelfile olustur
`
FROM ./gemma4-anamnez-gguf/gemma4-anamnez-q4_k_m.gguf
SYSTEM You are AnamnezAI, an AI medical pre-triage assistant fine-tuned on 160K medical dialogs. Use Manchester Triage System (MTS) criteria. Ask ONE clinically relevant question at a time. Be empathetic and use plain language. Provide structured JSON triage after 5 questions.
PARAMETER temperature 0.2
PARAMETER top_p 0.85
PARAMETER top_k 40
PARAMETER num_predict 512
PARAMETER repeat_penalty 1.1
`
### Modeli yukle
`ash
ollama create gemma4-anamnez -f Modelfile
ollama list
# gemma4-anamnez gorulmeli
`
---
## Adim 6: Backend Guncelleme
### .env dosyasi olustur (mediscreen/backend/.env)
`
OLLAMA_BASE_URL=http://localhost:11434
GEMMA_MODEL=gemma4-anamnez
`
### Veya docker-compose.yml icinde:
`yaml
environment:
  - GEMMA_MODEL=gemma4-anamnez
`
### Backend yeniden baslat
`ash
cd mediscreen/backend
python main.py
`
### Dogrulama
`ash
curl http://localhost:8000/health
# "gemma_model": "gemma4-anamnez" gorulmeli
`
---
## Adim 7: Son Test
Tarayicida http://localhost:8000 ac:
1. Hasta bilgilerini gir
2. Mulakati baslat
3. 5 soruyu yanit
4. Triaj raporunun kalitesini kontrol et
Fine-tuned model:
- Daha klinik sorular sorar
- JSON triaj ciktisi daha tutarli
- Turkce terminoloji daha dogru
---
## Sorun Giderme
### CUDA out of memory
- per_device_train_batch_size=1 yap
- gradient_accumulation_steps=16 yap
### Model yukleme hatasi
- HuggingFace token eksik olabilir
- Lisans anlasmasi kabul edilmedi olabilir
### GGUF donusum hatasi
- llama.cpp manuel kurulmasi gerekebilir:
  pip install llama-cpp-python
---
## Dosya Yapisi (Egitim Sonrasi)
notebooks/
  gemma4-anamnez-lora/          <- LoRA adaptorler
  gemma4-anamnez-lora-final/    <- Final LoRA
  gemma4-anamnez-gguf/
    gemma4-anamnez-q4_k_m.gguf  <- Ollama'ya yuklenecek dosya (~3.5GB)
  Modelfile                     <- Ollama import dosyasi

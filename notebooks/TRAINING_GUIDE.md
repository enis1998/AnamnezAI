# AnamnezAI — Gemma 4 Fine-Tuning Guide
## Step-by-Step Training with RTX 5070 Ti

---

## Requirements

| Requirement | Detail |
|-------------|--------|
| GPU | RTX 5070 Ti (16 GB VRAM) |
| RAM | 32 GB+ recommended |
| Disk | 50 GB free space |
| OS | Windows 11 / Ubuntu 22.04 |
| Python | 3.11+ |
| CUDA | 12.4+ |

---

## Step 1: Setup

On the training machine:

```bash
git clone https://github.com/enis1998/AnamnezAI.git
cd AnamnezAI/mediscreen/notebooks
python setup_training_env.py
```

---

## Step 2: HuggingFace Token (required for Gemma 4 access)

Gemma 4 requires an accepted licence agreement:

1. Go to https://huggingface.co/google/gemma-4-4b-it
2. Accept the licence agreement
3. Create a HuggingFace API token: https://huggingface.co/settings/tokens
4. Update the token line in the notebook:
   ```
   token='hf_xxxxxxxxxxxxx'
   ```

---

## Step 3: Start Training

```bash
jupyter notebook train_gemma4_medical.ipynb
```

Or directly with Python:

```bash
python -c "import nbformat; exec(open('train_gemma4_medical.ipynb').read())"
```

### Estimated Times (RTX 5070 Ti)

| Dataset Size | Epochs | Duration |
|-------------|--------|----------|
| 40K samples | 2 | ~2–3 hours |
| 80K samples | 2 | ~4–6 hours |
| 160K samples | 2 | ~8–12 hours |

---

## Step 4: GGUF Conversion

Handled automatically inside the notebook. Manually:

```bash
# Output: gemma4-anamnez-gguf/gemma4-anamnez-q4_k_m.gguf
# Size: ~3.5 GB (q4_k_m quality)
```

---

## Step 5: Import into Ollama

After training completes, add the model to Ollama:

### Create Modelfile

```
FROM ./gemma4-anamnez-gguf/gemma4-anamnez-q4_k_m.gguf
SYSTEM You are AnamnezAI, an AI medical pre-triage assistant fine-tuned on 160K medical dialogs. Use Manchester Triage System (MTS) criteria. Ask ONE clinically relevant question at a time. Be empathetic and use plain language. Provide structured JSON triage after 5 questions.
PARAMETER temperature 0.2
PARAMETER top_p 0.85
PARAMETER top_k 40
PARAMETER num_predict 512
PARAMETER repeat_penalty 1.1
```

### Load the model

```bash
ollama create gemma4-anamnez -f Modelfile
ollama list
# gemma4-anamnez should appear
```

---

## Step 6: Update Backend

### Create .env file (mediscreen/backend/.env)

```
OLLAMA_BASE_URL=http://localhost:11434
GEMMA_MODEL=gemma4-anamnez
```

### Or in docker-compose.yml:

```yaml
environment:
  - GEMMA_MODEL=gemma4-anamnez
```

### Restart backend

```bash
cd mediscreen/backend
python main.py
```

### Verify

```bash
curl http://localhost:8000/health
# "gemma_model": "gemma4-anamnez" should appear
```

---

## Step 7: Final Test

Open http://localhost:8000 in a browser:

1. Enter patient information
2. Start the interview
3. Answer the 5 questions
4. Check the quality of the triage report

The fine-tuned model will:
- Ask more clinically precise questions
- Produce more consistent JSON triage output
- Handle Turkish medical terminology more accurately

---

## Troubleshooting

### CUDA out of memory
- Set `per_device_train_batch_size=1`
- Set `gradient_accumulation_steps=16`

### Model loading error
- HuggingFace token may be missing
- Licence agreement may not have been accepted

### GGUF conversion error
- llama.cpp may need to be installed manually:
  ```bash
  pip install llama-cpp-python
  ```

---

## Output File Structure (After Training)

```
notebooks/
  gemma4-anamnez-lora/           ← LoRA adapters
  gemma4-anamnez-lora-final/     ← Final LoRA
  gemma4-anamnez-gguf/
    gemma4-anamnez-q4_k_m.gguf  ← File to load into Ollama (~3.5 GB)
  Modelfile                      ← Ollama import file
```

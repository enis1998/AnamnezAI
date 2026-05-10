FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Kalıcı veri dizini oluştur (DB + ChromaDB mount noktaları)
RUN mkdir -p /app/data /app/chroma_db

# Python bağımlılıkları — önce CPU-only torch yükle (CUDA sürümü ~1.5GB yerine ~200MB)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Backend kaynak kodları
COPY backend/main.py ./main.py
COPY backend/auth.py ./auth.py
COPY backend/rag.py ./rag.py

# Frontend statik dosyaları
COPY frontend/ /app/frontend/

EXPOSE 8000

# DB_PATH kalıcı veri dizinini göstersin (volume mount'tan gelir)
ENV DB_PATH=/app/data/anamnezai.db
ENV CHROMA_DIR=/app/chroma_db

# Docker healthcheck — /healthz lightweight endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# Uvicorn doğrudan çalıştır (production modu — no reload)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

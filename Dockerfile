FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Kalıcı veri dizini oluştur (ChromaDB mount noktası)
RUN mkdir -p /app/chroma_db

# Python bağımlılıkları — önce CPU-only torch yükle (CUDA sürümü ~1.5GB yerine ~200MB)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Backend kaynak kodlarının tamamı (safety.py, database.py, auth.py, rag.py, main.py …)
# tests/ ve __pycache__/ .dockerignore ile dışarıda bırakılır
COPY backend/ /app/

# Frontend statik dosyaları
COPY frontend/ /app/frontend/

EXPOSE 8000

# ChromaDB konumu
ENV CHROMA_DIR=/app/chroma_db

# Docker healthcheck — /healthz lightweight endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# Uvicorn doğrudan çalıştır (production modu — no reload)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

#!/usr/bin/env python3
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.200.9.11', username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj',
            timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return (out + err).strip()

sftp = ssh.open_sftp()

# Sunucudaki docker-compose.yml'i güncelle (postgres ports kaldırıldı, backend 8001)
new_compose = """version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: anamnezai
      POSTGRES_USER: anamnezai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-anamnezai_secret}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U anamnezai -d anamnezai"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8001:8000"
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      - GEMMA_MODEL=${GEMMA_MODEL:-gemma4:e4b}
      - MEDGEMMA_MODEL=${MEDGEMMA_MODEL:-medgemma:4b}
      - FRONTEND_DIR=/app/frontend
      - RAG_ENABLED=${RAG_ENABLED:-true}
      - OLLAMA_NUM_GPU=${OLLAMA_NUM_GPU:-99}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-change_me_in_production}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET:-}
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=anamnezai
      - POSTGRES_USER=anamnezai
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-anamnezai_secret}
    volumes:
      - chroma_data:/app/chroma_db
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

volumes:
  postgres_data:
  chroma_data:
"""

with sftp.file('/srv/anamnezai/docker-compose.yml', 'w') as f:
    f.write(new_compose)
print("docker-compose.yml guncellendi")
sftp.close()

print("\n=== Compose down & up ===")
print(run('cd /srv/anamnezai && docker compose down 2>&1'))
time.sleep(2)
print(run('cd /srv/anamnezai && docker compose up -d 2>&1', timeout=180))

print("\n=== 20 saniye bekle ===")
time.sleep(20)

print("\n=== Container durumlari ===")
print(run('docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}" | grep anamnez'))

print("\n=== Backend logs ===")
print(run('docker logs anamnezai-backend-1 --tail 25 2>&1'))

print("\n=== Health check ===")
result = run('curl -s http://localhost:8001/health 2>&1')
print(result)

ssh.close()


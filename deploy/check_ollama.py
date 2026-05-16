#!/usr/bin/env python3
"""check_ollama.py — Ollama durumunu kapsamlı kontrol"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=30):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

print("=== 1. Ollama process durumu ===")
print(run("systemctl is-active ollama 2>/dev/null || pgrep -a ollama | head -5"))

print("\n=== 2. Ollama port dinliyor mu? ===")
print(run("ss -tlnp | grep 11434"))

print("\n=== 3. host.docker.internal çözümlemesi ===")
print(run("docker exec anamnezai-backend-1 getent hosts host.docker.internal 2>&1 || echo 'ÇÖZÜMLENEMEDI'"))

print("\n=== 4. Container içinden Ollama bağlantısı ===")
print(run("docker exec anamnezai-backend-1 curl -s --max-time 5 http://host.docker.internal:11434/api/tags 2>&1 | head -c 200"))

print("\n=== 5. Ollama localhost direkt ===")
print(run("curl -s --max-time 5 http://localhost:11434/api/tags | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(m[\"name\"]) for m in d[\"models\"]]' 2>&1"))

print("\n=== 6. Container dışından Ollama /api/chat testi ===")
body = '{"model":"gemma4:e4b","messages":[{"role":"user","content":"Merhaba"}]}'
print(run(f"curl -s --max-time 30 -X POST http://localhost:11434/api/chat -H 'Content-Type: application/json' -d '{body}' | head -c 200"))

print("\n=== 7. Container içinden Ollama /api/chat testi ===")
print(run(f"docker exec anamnezai-backend-1 curl -s --max-time 30 -X POST http://host.docker.internal:11434/api/chat -H 'Content-Type: application/json' -d '{body}' | head -c 200"))

print("\n=== 8. main.py OLLAMA_BASE_URL nedir? ===")
print(run("docker exec anamnezai-backend-1 python3 -c 'import os; print(os.getenv(\"OLLAMA_BASE_URL\",\"TANIMI_YOK\"))' 2>&1"))

print("\n=== 9. Backend env değişkenleri ===")
print(run("docker exec anamnezai-backend-1 env | grep -iE 'ollama|model|host' | head -10"))

print("\n=== 10. Ollama tam URL konfigurasyonu ===")
print(run("grep -n 'OLLAMA_BASE_URL\|OLLAMA_HOST\|host.docker' /srv/anamnezai/backend/main.py | head -10"))

print("\n=== 11. Docker compose env ayarlari ===")
print(run("cat /srv/anamnezai/docker-compose.yml | grep -A3 -E 'OLLAMA|environment' | head -30"))

client.close()
print("\nBitti.")


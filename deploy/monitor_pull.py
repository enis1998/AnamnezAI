#!/usr/bin/env python3
"""
monitor_and_complete.py
- Ollama model pull durumunu izle
- Pull tamamlandığında warmup yap
- favicon.ico dur kontrolü
"""
import paramiko, time

HOST = "10.200.9.11"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace').strip()
    err = stderr.read().decode('utf-8', 'replace').strip()
    return out or err

BASE = "http://localhost:8001"

print("=" * 60)
print("📊 Ollama Model Pull ve Sistem Durumu İzleme")
print("=" * 60)

# Pull log
print("\n⬇️  Ollama pull durumu:")
pull_log = run("tail -10 /var/log/ollama_pull.log 2>/dev/null")
print(pull_log or "Log yok")

# Model listesi
print("\n📦 Mevcut Ollama modelleri:")
models = run("ollama list 2>&1")
print(models)

# Model yüklü mü?
is_ready = "gemma4:e4b" in models

print(f"\n{'✅ Model HAZIR!' if is_ready else '⏳ Model henüz indirilmiyor...'}")

if is_ready:
    print("\n🔥 Model warmup yapılıyor...")
    warmup = run(f"curl -s --max-time 60 -X POST '{BASE}/api/warmup' -H 'Content-Type: application/json' -d '{{}}'", timeout=65)
    print(f"  Warmup: {warmup[:200]}")

    print("\n🧪 Basit AI testi:")
    body = '{"patient_name":"Test Hasta","age":35,"gender":"Erkek","language":"tr"}'
    result = run(f"curl -s --max-time 10 -X POST '{BASE}/api/session/start' -H 'Content-Type: application/json' -d '{body}'")
    print(f"  session/start: {result[:200]}")
else:
    print("\n  Pull devam ediyor — birkaç dakika içinde tamamlanacak.")
    print("  Pull tamamlandığında bu scripti tekrar çalıştırın.")

# Genel sistem durumu
print("\n📋 Genel Sistem Durumu:")
for ep in ["/healthz", "/api/public/landing-metrics", "/api/demo/cases", "/robots.txt", "/sitemap.xml"]:
    out = run(f"curl -s --max-time 5 '{BASE}{ep}' | head -c 60")
    ok = len(out) > 5 and '404' not in out and 'Not Found' not in out
    print(f"  {'✅' if ok else '❌'} {ep:40s} {out[:50]}")

# Backend container durumu
print("\n🐳 Container durumu:")
print(run("docker ps --format 'table {{.Names}}\t{{.Status}}' | grep anamnezai"))

client.close()
print("\nTamamlandı.")


#!/usr/bin/env python3
"""test_session_answer.py — Session answer AI testi"""
import paramiko, json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=90):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

BASE = "http://localhost:8001"

# Yeni session başlat
print("Session başlatılıyor...")
body = '{"patient_name":"Mehmet Demir","age":52,"gender":"Erkek","language":"tr"}'
r = run(f"curl -s --max-time 10 -X POST '{BASE}/api/session/start' -H 'Content-Type: application/json' -d '{body}'")
d = json.loads(r)
sid = d['session_id']
print(f"Session ID: {sid}")
print(f"İlk soru: {d['question']}")

# Cevabı gönder (Gemma 4 çağrısı)
print("\nCevap gönderiliyor (Gemma 4 çağrısı - 90s timeout)...")
body2 = json.dumps({"session_id": sid, "answer": "göğüs ağrısı ve sol kola yayılıyor, nefes darlığım var"})
r2 = run(f"curl -s --max-time 80 -X POST '{BASE}/api/session/answer' -H 'Content-Type: application/json' -d '{body2}'", timeout=85)
print(f"Ham yanıt: {r2[:300]}")

try:
    d2 = json.loads(r2)
    print(f"\nSonraki soru: {d2.get('question', 'YOK')}")
    print(f"Adım: {d2.get('step')}/{d2.get('total_steps')}")
    print("✅ Session answer ÇALIŞIYOR!")
except Exception as e:
    print(f"❌ Parse hatası: {e}")

client.close()


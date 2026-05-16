#!/usr/bin/env python3
"""check_404s.py — 404 veren dosyaları bul ve hangisi gerekli"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=30):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

BASE = "http://localhost:8001"

# Tüm 404'leri listele (son 1000 satır)
print("=== Son 1000 nginx logundan 404 istekleri ===")
r = run("tail -1000 /var/log/nginx/access.log | awk '$9==404 {print $7}' | sort | uniq -c | sort -rn | head -30")
print(r)

# CSS/JS dosyaları HTML'de aranıyor mu?
print("\n=== support_parent.css hangi HTML'de referans var? ===")
r2 = run("grep -rl 'support_parent.css' /srv/anamnezai/frontend/ 2>/dev/null")
print(r2 or "Yok — farklı siteden gelen bot/test")

print("\n=== assets/js/auth.js hangi HTML'de referans var? ===")
r3 = run("grep -rl 'assets/js/auth' /srv/anamnezai/frontend/ 2>/dev/null")
print(r3 or "Yok — farklı siteden gelen bot/test")

print("\n=== robots.txt var mi? ===")
r4 = run("test -f /srv/anamnezai/frontend/robots.txt && echo MEVCUT || echo EKSIK")
print(r4)

print("\n=== channel endpoint uzun timeout testi ===")
body = '{"channel":"whatsapp_demo","external_user_id":"test-long-456","message":"bas agrim var","language":"tr"}'
result = run(f"curl -s --max-time 45 -X POST '{BASE}/api/channel/intake/message' -H 'Content-Type: application/json' -d '{body}'", timeout=50)
print(result[:600] if result else "ZAMAN ASIMI / BOS")

print("\n=== Demo cases sayisi ===")
r5 = run(f"curl -s --max-time 5 '{BASE}/api/demo/cases' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d[\"cases\"]),\"adet demo case\")'")
print(r5)

print("\n=== Eksik API endpoint kontrolu ===")
endpoints_to_check = [
    "/api/evaluation",
    "/api/channel/intake/message",
    "/api/offline-proof",
    "/api/public/landing-metrics",
    "/api/warmup",
]
for ep in endpoints_to_check:
    if "channel" in ep:
        # channel için sadece route kontrolu
        route_exists = run(f"curl -sI --max-time 3 -X POST '{BASE}{ep}' | head -1")
        print(f"  {ep}: {route_exists[:80]}")
    else:
        code = run(f"curl -sI --max-time 5 '{BASE}{ep}' | head -1")
        print(f"  {ep}: {code[:80]}")

client.close()
print("\nBitti.")



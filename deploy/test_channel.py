#!/usr/bin/env python3
"""test_channel.py — Channel endpoint test"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=20):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

BASE = "http://localhost:8001"

print("=== /api/channel/intake/message TEST ===")
body = '{"channel":"whatsapp_demo","external_user_id":"test-123","message":"bas agrim var","language":"tr"}'
result = run(f"curl -s --max-time 15 -X POST '{BASE}/api/channel/intake/message' -H 'Content-Type: application/json' -d '{body}'")
print(result[:500])

print("\n=== Tum endpoint listesi (app routes) ===")
routes = run("docker exec anamnezai-backend-1 python -c \"from main import app; [print(r.path) for r in app.routes if hasattr(r,'path')]\" 2>&1 | grep channel")
print(routes)

print("\n=== Nginx son 50 satir (site hatasi) ===")
r2 = run("tail -50 /var/log/nginx/access.log | grep -v '/health'")
print(r2[-1000:] if r2 else "Yok")

print("\n=== 404 olan istekler (son 500 satir) ===")
r3 = run("tail -500 /var/log/nginx/access.log | awk '$9==404'")
print(r3[-800:] if r3 else "404 yok")

client.close()
print("\nBitti.")


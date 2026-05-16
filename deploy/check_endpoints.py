#!/usr/bin/env python3
"""check_endpoints.py — Eksik endpoint ve hata tespiti"""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=20):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

BASE = "http://localhost:8001"

print("=== /api/evaluation endpoint ===")
print(run(f"curl -s --max-time 8 {BASE}/api/evaluation")[:300])

print("\n=== channel_demo backend arama ===")
print(run("grep -n channel_demo /srv/anamnezai/backend/main.py | head -10"))

print("\n=== evaluation.html API cagrilari ===")
print(run("grep -oE '/api/[a-zA-Z/_-]+' /srv/anamnezai/frontend/evaluation.html | sort -u | head -20"))

print("\n=== channel_demo.html API cagrilari ===")
print(run("grep -oE '/api/[a-zA-Z/_-]+' /srv/anamnezai/frontend/channel_demo.html | sort -u | head -20"))

print("\n=== GDPR endpoint varlik ===")
print(run("grep -n gdpr /srv/anamnezai/backend/main.py | head -10"))

print("\n=== Son 404/422/500 nginx hatalari ===")
print(run("tail -200 /var/log/nginx/access.log | grep -E '\" [45][0-9][0-9] ' | grep lifetrack | tail -20"))

print("\n=== Backend 422/500 son 20 ===")
print(run("docker logs anamnezai-backend-1 --tail 50 2>&1 | tail -20"))

print("\n=== main.py son satirlar (4750+) ===")
print(run("tail -40 /srv/anamnezai/backend/main.py"))

client.close()
print("\nBitti.")


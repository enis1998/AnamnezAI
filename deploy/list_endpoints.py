#!/usr/bin/env python3
"""Mevcut API endpoint'lerini listele"""
import paramiko, json

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

_, o, _ = ssh.exec_command("curl -sf http://localhost:8000/openapi.json 2>/dev/null")
raw = o.read().decode()

if raw:
    d = json.loads(raw)
    print("=== Mevcut POST endpoint'ler ===")
    for path, v in sorted(d.get("paths", {}).items()):
        if "post" in v:
            print(f"  POST {path}")
    print(f"\nToplam: {len(d.get('paths', {}))} endpoint")
else:
    print("openapi.json alinamadi")
    # Ana sayfayi kontrol et
    _, o2, _ = ssh.exec_command("curl -sf http://localhost:8000/health 2>/dev/null")
    print("Health:", o2.read().decode()[:200])

ssh.close()


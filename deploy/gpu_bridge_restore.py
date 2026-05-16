#!/usr/bin/env python3
"""
Sunucunun OLLAMA_BASE_URL'sini CPU moduna (host.docker.internal) geri alir.
Kullanim: python gpu_bridge_restore.py
"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"
DEFAULT_URL = "http://host.docker.internal:11434"

print(f"[Server] CPU moduna donuluyor: {DEFAULT_URL}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

_, o, _ = ssh.exec_command(
    f"cd /srv/anamnezai && "
    f"sed -i 's|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL={DEFAULT_URL}|' .env && "
    f"docker compose up -d --no-deps --force-recreate backend 2>&1 | tail -3"
)
print(o.read().decode().strip())
ssh.close()
print("[Done] Sunucu CPU moduna dondu.")


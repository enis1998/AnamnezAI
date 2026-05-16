#!/usr/bin/env python3
"""Backend hata detayları"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

# 500 hatasinin detayini bul
_, o, _ = ssh.exec_command("docker logs anamnezai-backend-1 2>&1 | grep -A 10 'Internal Server Error\\|Traceback\\|Error\\|Exception' | tail -40")
print(o.read().decode())

print("\n--- Tunnel URL test (server side) ---")
# Sunucudan tünel URL'ye doğrudan test
_, o2, _ = ssh.exec_command("cat /srv/anamnezai/.env | grep OLLAMA")
url_line = o2.read().decode().strip()
print(f"OLLAMA URL: {url_line}")

if 'trycloudflare' in url_line:
    tunnel_url = url_line.split('=')[1].strip()
    _, o3, _ = ssh.exec_command(f"curl -sf --max-time 10 {tunnel_url}/api/tags 2>/dev/null | head -100")
    tunnel_resp = o3.read().decode()
    print(f"Tunnel test: {tunnel_resp[:200] if tunnel_resp else '(bos - tünel ulasilamaz?)'}")

ssh.close()


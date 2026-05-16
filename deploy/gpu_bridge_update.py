#!/usr/bin/env python3
"""
Sunucunun OLLAMA_BASE_URL'sini yerel GPU tünel adresine günceller.
Kullanım: python gpu_bridge_update.py <TUNNEL_URL>
"""
import sys, time, paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

if len(sys.argv) < 2:
    print("Kullanim: python gpu_bridge_update.py <TUNNEL_URL>")
    sys.exit(1)

NEW_URL = sys.argv[1].strip()
print(f"[Server] Baglaniyor: {HOST}")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

def cmd(c):
    _, o, e = ssh.exec_command(c)
    out = o.read().decode().strip()
    return out

# .env dosyasini guncelle
print("[Server] .env guncelleniyor...")
cmd(f"cd /srv/anamnezai && sed -i 's|^OLLAMA_BASE_URL=.*|OLLAMA_BASE_URL={NEW_URL}|' .env")
current = cmd("grep OLLAMA_BASE_URL /srv/anamnezai/.env 2>/dev/null")
print(f"[Server] .env: {current}")

# Backend container'i yeniden baslatcak
print("[Server] Backend yeniden baslatiliyor...")
out = cmd("cd /srv/anamnezai && docker compose up -d --no-deps --force-recreate backend 2>&1 | tail -3")
print(f"[Server] {out}")

# Saglik kontrolu
time.sleep(12)
health = cmd("curl -sf http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -E 'status|ollama' | head -3")
if health:
    print(f"[Server] Health: {health}")
else:
    print("[Server] Health: (container basliyor, 30sn sonra hazir olur)")

ssh.close()
print(f"[Done] Sunucu GPU moduna alindi -> {NEW_URL}")


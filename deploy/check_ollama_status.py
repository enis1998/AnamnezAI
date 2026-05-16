#!/usr/bin/env python3
"""Sunucudaki mevcut .env ve Ollama durumunu göster"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

def cmd(c):
    _, o, e = ssh.exec_command(c)
    return o.read().decode().strip()

print("=== Mevcut .env (OLLAMA ve model ayarları) ===")
print(cmd("grep -E 'OLLAMA|GEMMA|MODEL' /srv/anamnezai/.env 2>/dev/null || echo '(.env yok veya bos)'"))

print("\n=== Container env (canlı değerler) ===")
print(cmd("docker exec anamnezai-backend-1 env | grep -E 'OLLAMA|GEMMA|MODEL' 2>/dev/null"))

print("\n=== Ollama host'ta çalışıyor mu? ===")
print(cmd("curl -sf http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(m['name']) for m in d.get('models',[])]\" 2>/dev/null || echo '(ollama host makinede çalışmıyor)'"))

print("\n=== Son 5 satır backend log (hata var mı?) ===")
print(cmd("docker logs anamnezai-backend-1 --tail 5 2>&1"))

ssh.close()


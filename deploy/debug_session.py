#!/usr/bin/env python3
"""Session/start endpoint test"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

# Test session start
_, o, e = ssh.exec_command(
    "curl -sv -X POST http://localhost:8000/api/session/start "
    "-H 'Content-Type: application/json' "
    "-d '{\"lang\":\"tr\"}' 2>&1"
)
out = o.read().decode()
err = e.read().decode()
print("STDOUT:", out[:500])
print("STD-combined:", err[:200] if err else "")

# Kontrol: hangi endpointler var?
print("\n--- Available /api/session routes ---")
_, o2, _ = ssh.exec_command("curl -sf http://localhost:8000/openapi.json 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin); [print(k) for k in d['paths'] if 'session' in k]\"")
print(o2.read().decode())

ssh.close()


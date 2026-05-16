#!/usr/bin/env python3
"""Son backend loglarını göster"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

_, o, _ = ssh.exec_command("docker logs anamnezai-backend-1 --tail 25 2>&1")
print(o.read().decode())
ssh.close()


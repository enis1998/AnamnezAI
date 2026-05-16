#!/usr/bin/env python3
"""Sunucudaki container ve port durumunu incele"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

def cmd(c):
    _, o, _ = ssh.exec_command(c)
    return o.read().decode().strip()

print("=== Docker container'lar ===")
print(cmd("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"))

print("\n=== Port 8000 ne dinliyor? ===")
print(cmd("ss -tlnp | grep 8000 || netstat -tlnp 2>/dev/null | grep 8000"))

print("\n=== /srv altindaki projeler ===")
print(cmd("ls -la /srv/"))

print("\n=== AnamnezAI container log (son 10) ===")
containers = cmd("docker ps --format '{{.Names}}' | grep -i anamnez")
if containers:
    for c in containers.split('\n'):
        print(f"Container: {c}")
        print(cmd(f"docker logs {c} --tail 5 2>&1"))
else:
    print("AnamnezAI container bulunamadi")
    print("Tüm container'lar:", cmd("docker ps --format '{{.Names}}'"))

ssh.close()


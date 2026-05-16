#!/usr/bin/env python3
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.200.9.11', username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj',
            timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return (out + err).strip()

print("=== BACKEND CRASH LOGS ===")
print(run('docker logs anamnezai-backend-1 --tail 60 2>&1'))

print("\n=== DOCKER COMPOSE YML ===")
print(run('cat /srv/anamnezai/docker-compose.yml'))

print("\n=== ENV DOSYASI ===")
print(run('cat /srv/anamnezai/.env 2>/dev/null | grep -v PASSWORD | grep -v SECRET | grep -v KEY'))

ssh.close()


#!/usr/bin/env python3
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.200.9.11', username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj',
            timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return (out + err).strip()

print("=== Docker Compose başlatılıyor ===")
print(run('cd /srv/anamnezai && docker compose up -d 2>&1', timeout=120))

print("\n=== 10 saniye bekleniyor ===")
time.sleep(10)

print("\n=== Container durumları ===")
print(run('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep anamnez'))

print("\n=== Port 8001 kontrolü ===")
print(run('ss -tlnp | grep 8001'))

print("\n=== Health check ===")
print(run('curl -s http://localhost:8001/health 2>&1 | head -5'))

ssh.close()
print("\nTAMAMLANDI")


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

print("=== DOCKER NETWORKS ===")
print(run('docker network ls'))

print("\n=== BACKEND NETWORK INSPECT ===")
print(run('docker inspect anamnezai-backend-1 --format "{{json .NetworkSettings.Networks}}" 2>/dev/null || echo "container not found"'))

print("\n=== POSTGRES NETWORK INSPECT ===")
print(run('docker inspect anamnezai-postgres-1 --format "{{json .NetworkSettings.Networks}}" 2>/dev/null || echo "container not found"'))

print("\n=== Eski container sil ve yeniden olustur ===")
print(run('cd /srv/anamnezai && docker compose down 2>&1'))
time.sleep(3)
print(run('cd /srv/anamnezai && docker compose up -d --force-recreate 2>&1', timeout=120))

print("\n=== 15 saniye bekle ===")
time.sleep(15)

print("\n=== Container durumlari ===")
print(run('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep anamnez'))

print("\n=== Backend logs ===")
print(run('docker logs anamnezai-backend-1 --tail 20 2>&1'))

print("\n=== Health check ===")
print(run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>&1'))

ssh.close()


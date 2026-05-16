#!/usr/bin/env python3
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.200.9.11', username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj',
            timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=20):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return (out + err).strip()

print("=== DOCKER CONTAINERS ===")
print(run('docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'))

print("\n=== NGINX STATUS ===")
print(run('systemctl is-active nginx'))
print(run('nginx -t 2>&1'))

print("\n=== NGINX CONFIG (proxy_pass) ===")
print(run('grep -r proxy_pass /etc/nginx/ 2>/dev/null | head -20'))

print("\n=== PORT DINLEME ===")
print(run('ss -tlnp | grep -E "8001|8000|80 |443"'))

print("\n=== BACKEND LOGS (son 40 satir) ===")
print(run('docker logs anamnezai-backend --tail 40 2>&1'))

print("\n=== NGINX ERROR LOG (son 20 satir) ===")
print(run('tail -20 /var/log/nginx/error.log 2>/dev/null'))

print("\n=== CURL TEST (localhost:8001) ===")
print(run('curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health 2>&1'))

ssh.close()


#!/usr/bin/env python3
"""Check nginx virtual host config for lifetrack.com.tr"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out or err

print("=== nginx sites-available / sites-enabled ===")
out = run("ls -la /etc/nginx/sites-enabled/ 2>/dev/null || ls -la /etc/nginx/conf.d/ 2>/dev/null")
print(out)

print("\n=== Virtual host for lifetrack ===")
out = run("grep -rl 'lifetrack' /etc/nginx/ 2>/dev/null")
print("Files:", out)
if out:
    for f in out.split('\n'):
        f = f.strip()
        if f:
            content = run(f"cat {f}")
            print(f"\n--- {f} ---")
            print(content[:3000])

print("\n=== proxy_pass configuration ===")
out = run("grep -rn 'proxy_pass' /etc/nginx/ 2>/dev/null")
print(out[:1000])

print("\n=== Server HTTPS check ===")
out = run("curl -sI --max-time 8 http://localhost:8001/ | head -2")
print("Direct 8001:", out)
out2 = run("curl -sI --max-time 8 https://lifetrack.com.tr/ 2>/dev/null | head -3")
print("lifetrack.com.tr (self):", out2 or "(empty - expected from within server)")
# Try checking if external IP port 443 responds
out3 = run("curl -sI --max-time 8 http://lifetrack.com.tr:80/ 2>/dev/null | head -3")
print("lifetrack.com.tr:80 (self):", out3 or "(empty)")

client.close()


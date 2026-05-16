#!/usr/bin/env python3
import paramiko, sys

PASSWORD = sys.argv[1] if len(sys.argv) > 1 else "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password=PASSWORD, timeout=15)

def run(cmd):
    _, stdout, stderr = client.exec_command(cmd, timeout=15)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

print("=== 1. Backend GOOGLE_CLIENT_ID env ===")
print(run("docker exec anamnezai-backend-1 env | grep GOOGLE"))

print("\n=== 2. google-auth kurulu mu? ===")
print(run("docker exec anamnezai-backend-1 pip show google-auth 2>&1 | head -5"))

print("\n=== 3. requirements.txt google ===")
print(run("grep -i google /srv/anamnezai/backend/requirements.txt"))

print("\n=== 4. /auth/google endpoint test ===")
r = run('curl -s -X POST http://localhost:8001/auth/google -H "Content-Type: application/json" -d \'{"credential":"test"}\' 2>&1')
print(r[:400])

print("\n=== 5. docker-compose.yml GOOGLE env ===")
print(run("grep -A2 -B2 GOOGLE /srv/anamnezai/docker-compose.yml"))

client.close()
print("\nBitti.")


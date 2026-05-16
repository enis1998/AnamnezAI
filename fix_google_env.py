import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
GOOGLE_CLIENT_ID='201244506846-m28jucbi8roj6io5126pabv8bmfcu71o.apps.googleusercontent.com'

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=30):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'  $ {cmd[:80]}')
    if out: print(f'  > {out[:300]}')
    return out

print('=== 1. Check current .env ===')
r('cat /srv/anamnezai/.env')

print('\n=== 2. Set GOOGLE_CLIENT_ID in .env ===')
# Read current .env
_,so,_=c.exec_command('cat /srv/anamnezai/.env', timeout=10)
env_content = so.read().decode('utf-8','replace')

# Update or add GOOGLE_CLIENT_ID
if 'GOOGLE_CLIENT_ID=' in env_content:
    # Replace existing
    lines = env_content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('GOOGLE_CLIENT_ID='):
            new_lines.append(f'GOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID}')
        else:
            new_lines.append(line)
    new_env = '\n'.join(new_lines)
else:
    new_env = env_content.rstrip() + f'\nGOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID}\n'

# Write back via echo
new_env_escaped = new_env.replace("'", "'\\''")
r(f"cat > /srv/anamnezai/.env << 'ENVEOF'\n{new_env}\nENVEOF")
r('grep GOOGLE /srv/anamnezai/.env')

print('\n=== 3. Restart backend container ===')
r('cd /srv/anamnezai && docker compose down backend && docker compose up -d backend', timeout=60)

print('\n=== 4. Wait 10s then verify ===')
import time; time.sleep(10)
r('docker exec anamnezai-backend-1 env | grep GOOGLE')
r('curl -s http://localhost:8000/healthz | head -c 100')

print('\n=== DONE ===')
c.close()


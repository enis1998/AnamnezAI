import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=20):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'$ {cmd[:100]}')
    if out: print(out[:2000])
    return out

print('=== nginx lifetrack.com.tr config ===')
r("cat '/etc/nginx/sites-enabled/lifetrack.com.tr'", timeout=30)

print('\n=== check FastAPI static mount ===')
r("docker exec anamnezai-backend-1 grep -n 'StaticFiles\\|mount\\|frontend' /app/main.py 2>/dev/null | head -20")

print('\n=== curl headers via nginx port 443 ===')
r("curl -sI -k https://lifetrack.com.tr/doctor.html 2>/dev/null | head -15")
r("curl -sI http://lifetrack.com.tr/doctor.html 2>/dev/null | head -15")

c.close()


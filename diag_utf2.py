import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=20):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'$ {cmd[:100]}')
    if out: print(out[:600])
    return out

print('=== nginx config ===')
r('cat /etc/nginx/sites-enabled/default 2>/dev/null || cat /etc/nginx/nginx.conf 2>/dev/null | head -80')
r('ls /etc/nginx/sites-enabled/ 2>/dev/null')
r('ls /etc/nginx/conf.d/ 2>/dev/null')

print('\n=== nginx content-type/charset settings ===')
r('grep -rn "charset\|add_header\|content.type\|html" /etc/nginx/sites-enabled/ 2>/dev/null | head -20')
r('grep -rn "charset\|add_header\|content.type\|html" /etc/nginx/conf.d/ 2>/dev/null | head -20')

print('\n=== Full nginx default site config ===')
r('cat /etc/nginx/sites-enabled/anamnezai 2>/dev/null || cat /etc/nginx/sites-enabled/lifetrack 2>/dev/null || cat /etc/nginx/sites-enabled/default 2>/dev/null', timeout=30)

print('\n=== Check BOM in file ===')
r("python3 -c \"with open('/srv/anamnezai/frontend/doctor.html','rb') as f: h=f.read(10); print('first bytes hex:', h.hex()); print('has BOM:', h[:3]==b'\\xef\\xbb\\xbf')\"")

print('\n=== HTTP response headers from localhost ===')
r('curl -si http://localhost:8000/doctor.html 2>/dev/null | head -20')

c.close()


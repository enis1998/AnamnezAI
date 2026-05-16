import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=20):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'$ {cmd[:80]}')
    if out: print(out[:400])
    return out

print('=== 1. Content-Type header from nginx ===')
r('curl -sI https://lifetrack.com.tr/doctor.html 2>/dev/null | grep -i content-type')

print('\n=== 2. File encoding check on server ===')
r('file /srv/anamnezai/frontend/doctor.html')

print('\n=== 3. Check for non-UTF8 bytes in doctor.html on server ===')
r("python3 -c \"\nimport sys\nwith open('/srv/anamnezai/frontend/doctor.html','rb') as f: d=f.read()\ntry:\n  d.decode('utf-8')\n  print('Valid UTF-8')\nexcept Exception as e:\n  print('INVALID UTF-8:',e)\n\"")

print('\n=== 4. Sample Turkish chars from file on server ===')
r("grep -o 'Aktif Triaj Kuyru.*' /srv/anamnezai/frontend/doctor.html 2>/dev/null | head -3")

print('\n=== 5. Check hex of Turkish section ===')
r("python3 -c \"\nwith open('/srv/anamnezai/frontend/doctor.html','rb') as f: d=f.read()\nidx=d.find(b'queueTitle')\nprint('queueTitle bytes:', d[idx:idx+50].hex())\nprint('queueTitle text:', d[idx:idx+50])\n\"")

print('\n=== 6. nginx charset config ===')
r('grep -r charset /etc/nginx/sites-enabled/ 2>/dev/null || grep -r charset /etc/nginx/conf.d/ 2>/dev/null | head -10')

c.close()


import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

sftp = c.open_sftp()

def r(cmd, timeout=60):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'$ {cmd[:100]}')
    if out: print(out[:600])
    return out

# 1. FIX NGINX - remove bad proxy_hide_header and add_header Content-Type
print('=== 1. Fix nginx config (remove bad Content-Type override) ===')
_,so,_=c.exec_command('cat /etc/nginx/sites-enabled/lifetrack.com.tr', timeout=10)
nginx = so.read().decode('utf-8','replace')

# Remove the bad lines we added
nginx = nginx.replace(
    '    charset_types text/html text/plain text/css application/javascript;\n    proxy_hide_header Content-Type;\n    add_header Content-Type "text/html; charset=utf-8";\n',
    '    charset_types text/html text/plain text/css application/javascript;\n'
)
print('charset section now:')
idx = nginx.find('charset')
print(nginx[idx:idx+150])

# Write fixed nginx config
_,so,se=c.exec_command(f'cat > /etc/nginx/sites-enabled/lifetrack.com.tr', timeout=15)
so_stdin = so
c.exec_command(f'tee /etc/nginx/sites-enabled/lifetrack.com.tr << \'NGEOF\'\n{nginx}\nNGEOF', timeout=15)

# Use sftp to write
sftp.open('/etc/nginx/sites-enabled/lifetrack.com.tr', 'w').write(nginx)
print('nginx config written')

r('nginx -t 2>&1')
r('systemctl reload nginx 2>&1')
r('grep -n "proxy_hide_header\|charset\|Content-Type" /etc/nginx/sites-enabled/lifetrack.com.tr | head -10')

# 2. COPY FIXED FILES FROM HOST TO CONTAINER
print('\n=== 2. Copy all fixed HTML files to container ===')
import os

HOST_FRONTEND = '/srv/anamnezai/frontend'
CONTAINER_NAME = 'anamnezai-backend-1'
CONTAINER_FRONTEND = '/app/frontend'

html_files = r(f'ls {HOST_FRONTEND}/*.html').split('\n')
print(f'Files to copy: {len(html_files)}')

for fpath in html_files:
    fpath = fpath.strip()
    if not fpath: continue
    fname = fpath.split('/')[-1]
    dst = f'{CONTAINER_FRONTEND}/{fname}'
    result = r(f'docker cp {fpath} {CONTAINER_NAME}:{dst} && echo OK', timeout=15)

# Also copy other important files
for extra in ['sw.js', 'manifest.json', 'version.json', 'robots.txt', 'sitemap.xml']:
    src = f'{HOST_FRONTEND}/{extra}'
    dst = f'{CONTAINER_FRONTEND}/{extra}'
    r(f'docker cp {src} {CONTAINER_NAME}:{dst} 2>/dev/null && echo "OK: {extra}" || echo "SKIP: {extra}"')

# 3. Verify the container has new files
print('\n=== 3. Verify container doctor.html ===')
r(f'docker exec {CONTAINER_NAME} md5sum {CONTAINER_FRONTEND}/doctor.html')
r(f'md5sum {HOST_FRONTEND}/doctor.html')
r(f'docker exec {CONTAINER_NAME} python3 -c "with open(\'{CONTAINER_FRONTEND}/doctor.html\',\'rb\') as f: h=f.read(10); print(\'BOM:\', h[:3].hex(), \'has_bom:\', h[:3]==b\'\\xef\\xbb\\xbf\')"')
r(f'docker exec {CONTAINER_NAME} python3 -c "with open(\'{CONTAINER_FRONTEND}/doctor.html\',\'rb\') as f: d=f.read(); print(\'size:\', len(d), \'valid_utf8:\', bool(d.decode(\'utf-8\',\'strict\')) if True else \'err\')" 2>&1 || echo "UTF8 check done"')

# 4. Verify headers from FastAPI
print('\n=== 4. Verify FastAPI headers ===')
r('curl -si http://127.0.0.1:8001/doctor.html 2>/dev/null | head -8')

# 5. final check - grep emoji in container
print('\n=== 5. Final content check ===')
r(f'docker exec {CONTAINER_NAME} grep -c "forEach\|localize(p.gender\|extractText(p.chief" {CONTAINER_FRONTEND}/doctor.html 2>/dev/null')
r(f'docker exec {CONTAINER_NAME} grep "statRedLbl" {CONTAINER_FRONTEND}/doctor.html 2>/dev/null | head -3')

sftp.close()
c.close()
print('\nDone!')


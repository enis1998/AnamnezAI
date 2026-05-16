import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=30):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'$ {cmd[:100]}')
    if out: print(out[:800])
    return out

# 1. Fix nginx: add charset utf-8 to the lifetrack.com.tr server block
print('=== 1. Add charset utf-8 to nginx config ===')

NGINX_CONF = '/etc/nginx/sites-enabled/lifetrack.com.tr'
_,so,_=c.exec_command(f'cat {NGINX_CONF}', timeout=10)
nginx_content = so.read().decode('utf-8','replace')

# Add charset after "ssl_session_timeout 1d;" in the https server block
# Also add it to the http block
if 'charset utf-8' not in nginx_content:
    # Find a good place to insert: after "ssl_prefer_server_ciphers on;"
    if 'add_header Strict-Transport-Security' in nginx_content:
        old_line = '    add_header Strict-Transport-Security'
        new_block = '    charset utf-8;\n\n    add_header Strict-Transport-Security'
        nginx_content = nginx_content.replace(old_line, new_block, 1)
        print('  charset utf-8 added before HSTS header')

    # Write new nginx config
    escaped = nginx_content.replace("'", "'\\''")
    r(f"cat > {NGINX_CONF} << 'NGEOF'\n{nginx_content}\nNGEOF")
    r(f'grep -n "charset" {NGINX_CONF}')
else:
    print('  charset already present in nginx config')

# 2. Test nginx config and reload
print('\n=== 2. Test and reload nginx ===')
r('nginx -t 2>&1')
r('systemctl reload nginx 2>&1')

# 3. Remove BOM from all frontend HTML files on server
print('\n=== 3. Remove BOM from frontend HTML files ===')
remove_bom_script = '''
import os, glob
fixed = 0
BOM = b"\\xef\\xbb\\xbf"
for f in glob.glob('/srv/anamnezai/frontend/*.html'):
    with open(f, 'rb') as fh: data = fh.read()
    if data.startswith(BOM):
        with open(f, 'wb') as fh: fh.write(data[3:])
        print("Removed BOM:", os.path.basename(f))
        fixed += 1
print(f"Total fixed: {fixed}")
'''

# Write and run the script
r("python3 -c \"\nimport os, glob\nBOM = b'\\xef\\xbb\\xbf'\nfixed = 0\nfor f in glob.glob('/srv/anamnezai/frontend/*.html'):\n    with open(f,'rb') as fh: data=fh.read()\n    if data.startswith(BOM):\n        with open(f,'wb') as fh: fh.write(data[3:])\n        print('BOM removed:', os.path.basename(f)); fixed+=1\nprint('Total:', fixed)\n\"", timeout=30)

# 4. Verify - check headers now
print('\n=== 4. Verify Content-Type headers ===')
import time; time.sleep(2)
r('curl -sI -k https://lifetrack.com.tr/doctor.html 2>/dev/null | grep -i "content-type\|charset"')

# 5. Also fix BOM in docker container
print('\n=== 5. Remove BOM from container files ===')
r("docker exec anamnezai-backend-1 python3 -c \"\nimport os, glob\nBOM = b'\\xef\\xbb\\xbf'\nfixed = 0\nfor f in glob.glob('/app/frontend/*.html'):\n    with open(f,'rb') as fh: data=fh.read()\n    if data.startswith(BOM):\n        with open(f,'wb') as fh: fh.write(data[3:])\n        print('BOM removed:', os.path.basename(f)); fixed+=1\nprint('Total container:', fixed)\n\" 2>&1", timeout=30)

print('\n=== 6. Check doctor.html first bytes after fix ===')
r("python3 -c \"with open('/srv/anamnezai/frontend/doctor.html','rb') as f: h=f.read(10); print('first bytes:', h.hex()); print('BOM gone:', not h.startswith(b'\\xef\\xbb\\xbf'))\"")

c.close()
print('\nDone!')


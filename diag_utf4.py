import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

def r(cmd, timeout=30):
    _,so,se=c.exec_command(cmd,timeout=timeout)
    out=(so.read()+se.read()).decode('utf-8','replace').strip()
    print(f'$ {cmd[:100]}')
    if out: print(out[:1000])
    return out

# 1. Check how container gets its frontend files
print('=== 1. Container volume mounts ===')
r("docker inspect anamnezai-backend-1 --format '{{json .Mounts}}' 2>/dev/null | python3 -c \"import json,sys; mounts=json.load(sys.stdin); [print(m.get('Source','?'),'->', m.get('Destination','?')) for m in mounts]\"")

# 2. Check if /app/frontend in container is bind-mount
print('\n=== 2. /app/frontend in container ===')
r('docker exec anamnezai-backend-1 ls -la /app/frontend/ 2>/dev/null | head -10')
r('docker exec anamnezai-backend-1 stat /app/frontend 2>/dev/null')

# 3. Check if files are same between host and container
print('\n=== 3. Compare host vs container doctor.html ===')
r("md5sum /srv/anamnezai/frontend/doctor.html 2>/dev/null")
r("docker exec anamnezai-backend-1 md5sum /app/frontend/doctor.html 2>/dev/null")

# 4. Check nginx charset header actually applied
print('\n=== 4. nginx charset verify ===')
r('grep -n "charset" /etc/nginx/sites-enabled/lifetrack.com.tr')
r("curl -si http://127.0.0.1:80/ 2>/dev/null | head -5 || echo 'N/A'")
r('curl -si http://127.0.0.1:8001/doctor.html 2>/dev/null | head -10')

# 5. Fix nginx - ensure charset applies to proxied content
print('\n=== 5. Fix nginx charset_types and proxy charset ===')
_,so,_=c.exec_command('cat /etc/nginx/sites-enabled/lifetrack.com.tr', timeout=10)
nginx = so.read().decode('utf-8','replace')

# Add charset_types after charset utf-8;
if 'charset_types' not in nginx:
    nginx = nginx.replace(
        '    charset utf-8;\n',
        '    charset utf-8;\n    charset_types text/html text/plain text/css application/javascript;\n    proxy_hide_header Content-Type;\n    add_header Content-Type "text/html; charset=utf-8";\n'
    )
    # Wait, that would apply to ALL routes - only add for HTML
    # Actually let's do it differently

# Direct approach: just set add_header for Content-Type in location /
# But that overrides everything... Let's target location block
# Best approach: use map or just in the main server block

# Actually simplest: in the https server block, add:
#   charset on; charset_types *;
# But that's deprecated. Best is:
#   add_header Content-Type "text/html; charset=UTF-8" always;  <- NO this overrides content-type wrong

# Actually for proxied content, we need:
# charset utf-8;
# charset_types text/html;
# These should already work... but let me check if there's proxy_pass content-type override issue

print('nginx content around charset:', nginx[nginx.find('charset'):nginx.find('charset')+200])

c.close()


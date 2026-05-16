import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj',
               timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd):
    _, o, e = client.exec_command(cmd, timeout=20)
    return (o.read()+e.read()).decode('utf-8','replace').strip()

# Container içi yapıyı bul
print('=== Container frontend paths ===')
print(run('docker exec anamnezai-backend-1 find /app -name "doctor.html" 2>/dev/null | head -5'))
print(run('docker exec anamnezai-backend-1 ls /app/ 2>/dev/null'))

# Host dosyasını kontrol et
print('\n=== Host lang-active check ===')
print(run('grep -c lang-active /srv/anamnezai/frontend/doctor.html 2>/dev/null || echo NOT_FOUND'))
print(run('grep -c lang-active /srv/anamnezai/frontend/index.html 2>/dev/null || echo NOT_FOUND'))

# Container doctor.html kontrol
print('\n=== Container doctor.html lang-active ===')
print(run('docker exec anamnezai-backend-1 grep -c lang-active /app/frontend/doctor.html 2>/dev/null || echo NOT_FOUND'))

client.close()
print('\nDone.')


import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj',
               timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd):
    _, o, e = client.exec_command(cmd, timeout=20)
    return (o.read()+e.read()).decode('utf-8','replace').strip()

for page in ['doctor.html', 'index.html', 'patient_dashboard.html']:
    r = run(f'grep -c lang-active /app/frontend/{page} 2>/dev/null || echo 0')
    print(f'{page}: lang-active refs = {r}')

r = run('grep -n "lang-active\\|classList.toggle" /app/frontend/doctor.html | head -20')
print('\ndoctor.html lang-active / classList lines:')
print(r)

client.close()
print('\nDone.')


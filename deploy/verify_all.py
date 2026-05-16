import paramiko

HOST = "10.200.9.11"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username="root", password="nWTGzzDqwyFyNJhqMhvcjEJj",
               timeout=15, look_for_keys=False, allow_agent=False)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    return (stdout.read() + stderr.read()).decode().strip()

print("=== SUNUCU DOSYA DURUMU ===")

# DL kontrolu
dl_line = run("grep -n 'const DL' /srv/anamnezai/frontend/doctor.html")
print(f"const DL satiri: {dl_line}")

# Orta satirlarda kopya DL kaligi var mi
middle_check = run("awk 'NR>500 && NR<1900' /srv/anamnezai/frontend/doctor.html | grep -c 'navTriage' || echo 0")
print(f"Orta satirlarda navTriage sayisi (0 olmali): {middle_check}")

# t() fonksiyon sayisi
tfn = run("grep -c 'function t(key' /srv/anamnezai/frontend/doctor.html")
print(f"function t(key) sayisi (1 olmali): {tfn}")

# setLang fonksiyonu var mi
sl = run("grep -c 'function setLang' /srv/anamnezai/frontend/doctor.html")
print(f"function setLang sayisi (1 olmali): {sl}")

# dlbtn butonlari var mi
btns = run("grep -c 'dlbtn-tr' /srv/anamnezai/frontend/doctor.html")
print(f"dlbtn-tr sayisi (1 olmali): {btns}")

# SW versiyonu
sw = run("grep -o 'anamnezai-v[0-9]*' /srv/anamnezai/frontend/sw.js")
print(f"SW versiyonu: {sw}")

# Container saglik
health = run("curl -s --max-time 3 http://localhost:8001/healthz 2>/dev/null | head -c 50")
print(f"Backend saglik: {health}")

client.close()
print("\n=== TAMAM ===")


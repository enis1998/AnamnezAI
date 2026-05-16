import paramiko
import sys

HOST = "10.200.9.11"
CREDENTIALS = [
    ("enis", "hx9ZCgKsLdFXVLnBMKdw"),
    ("root", "nWTGzzDqwyFyNJhqMhvcjEJj"),
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connected_user = None
for user, pw in CREDENTIALS:
    try:
        print(f"Deneniyor: {user}@{HOST} ...")
        client.connect(HOST, port=22, username=user, password=pw, timeout=10,
                       look_for_keys=False, allow_agent=False)
        print(f"BAGLANTI BASARILI: {user}")
        connected_user = user
        break
    except paramiko.AuthenticationException:
        print(f"  {user}: auth failed")
    except Exception as e:
        print(f"  {user}: {e}")

if not connected_user:
    print("Baglanti kurulamadi.")
    sys.exit(1)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

print("\n" + "="*50)
checks = [
    ("OS",         "cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION_ID'"),
    ("Kernel",     "uname -r"),
    ("RAM",        "free -h | grep Mem"),
    ("CPU",        "nproc && grep 'model name' /proc/cpuinfo | head -1"),
    ("Disk",       "df -h /"),
    ("GPU",        "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo NO_GPU"),
    ("Docker",     "docker --version 2>/dev/null || echo NO_DOCKER"),
    ("Compose",    "docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo NO_COMPOSE"),
    ("Ollama",     "ollama --version 2>/dev/null || echo NO_OLLAMA"),
    ("Nginx",      "nginx -v 2>&1 || echo NO_NGINX"),
    ("Certbot",    "certbot --version 2>/dev/null || echo NO_CERTBOT"),
    ("Port80",     "ss -tlnp | grep ':80 ' || echo NOT_LISTENING"),
    ("Port443",    "ss -tlnp | grep ':443 ' || echo NOT_LISTENING"),
    ("Port8000",   "ss -tlnp | grep ':8000 ' || echo NOT_LISTENING"),
    ("whoami",     "whoami && id"),
    ("sudo",       "sudo -n true 2>/dev/null && echo HAS_SUDO || echo NO_SUDO"),
]

for label, cmd in checks:
    out, err = run(cmd)
    print(f"[{label}] {out or err or 'empty'}")

client.close()
print("\nKONTROL TAMAMLANDI")

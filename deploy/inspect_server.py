import paramiko, sys

HOST = "10.200.9.11"
USER = "enis"
PASS = "hx9ZCgKsLdFXVLnBMKdw"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS, timeout=10,
               look_for_keys=False, allow_agent=False)
print("=== BAĞLANDI ===")

def run(cmd, sudo=False):
    if sudo:
        cmd = f"echo '{PASS}' | sudo -S {cmd} 2>/dev/null"
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out or err

# Mevcut durumu incele
checks = [
    ("Port 8000 ne?",       "ss -tlnp | grep 8000"),
    ("Docker containers",   "docker ps -a --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'"),
    ("Docker images",       "docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}'"),
    ("Docker volumes",      "docker volume ls"),
    ("Nginx sites",         "ls /etc/nginx/sites-enabled/"),
    ("Nginx default conf",  "cat /etc/nginx/sites-enabled/default 2>/dev/null | head -40"),
    ("/home/enis içeriği",  "ls /home/enis/"),
    ("/opt içeriği",        "ls /opt/ 2>/dev/null || echo empty"),
    ("Systemd servisler",   "systemctl list-units --type=service --state=running | grep -v '@' | head -20"),
    ("Ollama process",      "ps aux | grep ollama | grep -v grep || echo NO_OLLAMA_PROC"),
    ("curl port 8000",      "curl -s --max-time 3 http://localhost:8000/healthz 2>/dev/null | head -50 || echo NO_RESPONSE"),
    ("curl port 8000 root", "curl -s --max-time 3 http://localhost:8000/ 2>/dev/null | head -5 || echo NO_RESPONSE"),
]

for label, cmd in checks:
    result = run(cmd)
    print(f"\n[{label}]\n{result}")

client.close()
print("\n=== TAMAMLANDI ===")


import paramiko, sys, time

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"
ENIS_PASS = "hx9ZCgKsLdFXVLnBMKdw"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("=== ROOT BAĞLANDI ===")

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

# Mevcut durumu incele
print("\n[docker group]")
out, _ = run("getent group docker")
print(out)

print("\n[existing nginx sites]")
out, _ = run("ls /etc/nginx/sites-enabled/")
print(out)

print("\n[nginx aiboxio.com config snippet]")
out, _ = run("cat /etc/nginx/sites-enabled/aiboxio.com | head -30")
print(out)

print("\n[port 8000 process]")
out, _ = run("ss -tlnp | grep 8000 && fuser 8000/tcp 2>/dev/null | xargs ps -p 2>/dev/null | head -5")
print(out)

print("\n[which dirs avail for project]")
out, _ = run("ls /srv/ 2>/dev/null || echo empty; ls /home/ 2>/dev/null")
print(out)

print("\n[check lifetrack.com.tr DNS]")
out, _ = run("dig +short lifetrack.com.tr 2>/dev/null || host lifetrack.com.tr 2>/dev/null | head -3 || echo NO_DIG")
print(out)

client.close()
print("\n=== TAMAMLANDI ===")


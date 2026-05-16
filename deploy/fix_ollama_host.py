import paramiko, time

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Bağlandı")

def run(cmd, timeout=60, ignore_error=False):
    print(f"  $ {cmd[:100]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    combined = (out + err).strip()
    if combined:
        print(f"  {combined[:400]}")
    return out.strip(), err.strip()

# Pull durumu kontrol
print("\n📥 Model indirme durumu:")
run("tail -3 /var/log/ollama_pull.log")
run("ollama list 2>/dev/null")

# Ollama'yı 0.0.0.0'a bind et (Docker container'dan erişim için)
print("\n🔧 Ollama OLLAMA_HOST=0.0.0.0 yapılıyor...")

# Systemd service override
run("mkdir -p /etc/systemd/system/ollama.service.d/")
override_conf = """[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
"""
run(f"cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'\n{override_conf}\nEOF")
run("systemctl daemon-reload")
run("systemctl restart ollama")
time.sleep(5)

# Ollama dinleme kontrolü
out, _ = run("ss -tlnp | grep 11434")
print(f"  Ollama socket: {out}")

# Docker bridge IP'sini bul
out, _ = run("ip route | grep docker0 | head -1")
print(f"  Docker bridge: {out}")
docker_bridge_ip, _ = run("ip addr show docker0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1")
print(f"  Docker bridge IP: {docker_bridge_ip}")

# Ollama API yanıt kontrolü (host üzerinden)
run("curl -s http://localhost:11434/api/version")

# Docker container içinden host.docker.internal kontrolü
print("\n🔍 Docker container içinden Ollama erişim testi...")
anamnezai_container, _ = run("docker ps -qf name=anamnezai-backend", timeout=10)
if anamnezai_container:
    run(f"docker exec {anamnezai_container} curl -s --max-time 5 http://host.docker.internal:11434/api/version || echo FAILED")
else:
    print("  anamnezai-backend container bulunamadı!")

# Backend restart (Ollama bağlantısı için)
print("\n🔄 Backend yeniden başlatılıyor...")
run("cd /srv/anamnezai && docker compose restart backend", timeout=60)
time.sleep(15)

# Final health check
print("\n🏥 Final Health Check:")
for i in range(5):
    out, _ = run("curl -s --max-time 5 http://localhost:8001/health", ignore_error=True)
    if '"ollama"' in out:
        print(f"  Health: {out}")
        break
    print(f"  Bekleniyor ({i+1}/5)...")
    time.sleep(5)

# Model check
print("\n🦙 Ollama modeli:")
run("ollama list")

# Site erişim testi
print("\n🌐 Site testi:")
run("curl -s --max-time 5 http://localhost:8001/ | head -3")
run("curl -sk --max-time 5 https://localhost/ | head -3")

client.close()
print("\n✅ Bitti.")


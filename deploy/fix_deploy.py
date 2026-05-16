import paramiko, time

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Bağlandı")

def run(cmd, timeout=120, ignore_error=False):
    print(f"  $ {cmd[:100]}{'...' if len(cmd)>100 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    combined = (out + err).strip()
    if combined:
        print(f"  {combined[:300]}")
    return out.strip(), err.strip(), exit_code

# ─── FIX 1: PostgreSQL port çakışmasını çöz ──────────────────────────────────
print("\n🔧 FIX 1: PostgreSQL port 5433 yapılıyor (5432 meşgul)...")

# docker-compose.yml'den postgres port mapping kaldır (sadece internal bırak)
# sed ile "- \"5432:5432\"" satırını kaldır veya 5433 yap
run("sed -i 's/- \"5432:5432\"/- \"5433:5432\"/' /srv/anamnezai/docker-compose.yml")
out, _, _ = run("grep -A2 'postgres:$' /srv/anamnezai/docker-compose.yml | grep ports -A2")
print(f"  Postgres ports güncel: {out}")

# ─── FIX 2: Nginx — SSL sertifika üret (self-signed, certbot öncesi) ─────────
print("\n🔧 FIX 2: Self-signed SSL sertifikası üretiliyor...")
run("apt-get install -y ssl-cert 2>/dev/null || true", timeout=60, ignore_error=True)
run("make-ssl-cert generate-default-snakeoil --force-overwrite 2>/dev/null || true", ignore_error=True)

# snakeoil yoksa openssl ile oluştur
run("ls /etc/ssl/certs/ssl-cert-snakeoil.pem 2>/dev/null || openssl req -x509 -nodes -days 365 "
    "-newkey rsa:2048 "
    "-keyout /etc/ssl/private/ssl-cert-snakeoil.key "
    "-out /etc/ssl/certs/ssl-cert-snakeoil.pem "
    "-subj '/CN=lifetrack.com.tr/O=AnamnezAI/C=TR'", ignore_error=True)

run("ls -la /etc/ssl/certs/ssl-cert-snakeoil.pem /etc/ssl/private/ssl-cert-snakeoil.key")

# ─── FIX 3: Nginx test ve reload ─────────────────────────────────────────────
print("\n🔧 FIX 3: Nginx test...")
out, err, rc = run("nginx -t 2>&1", ignore_error=True)
if rc == 0:
    run("systemctl reload nginx")
    print("  ✅ Nginx reload tamam.")
else:
    print(f"  ❌ Nginx hata: {out} {err}")

# ─── FIX 4: docker compose yeniden başlat ────────────────────────────────────
print("\n🔧 FIX 4: Docker compose yeniden başlatılıyor...")
run("cd /srv/anamnezai && docker compose down", ignore_error=True)
time.sleep(3)
run("cd /srv/anamnezai && docker compose up -d", timeout=120)
time.sleep(15)

# Container durumu
print("\n📊 Container durumu:")
run("docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}' | grep -E 'anamnezai|NAME'")

# Port 8001 kontrolü
print("\n🏥 Port 8001 check:")
run("ss -tlnp | grep 8001")

# Backend yanıt kontrolü
print("\n🏥 Backend healthcheck...")
for i in range(5):
    out, _, rc = run("curl -s --max-time 5 http://localhost:8001/healthz", ignore_error=True)
    if out and rc == 0:
        print(f"  ✅ Backend yanıt veriyor: {out}")
        break
    print(f"  Bekleniyor... ({i+1}/5)")
    time.sleep(8)
else:
    # Log kontrol
    run("docker logs $(docker ps -qf name=anamnezai-backend) --tail 30 2>/dev/null || echo 'container yok'",
        ignore_error=True)

client.close()
print("\n✅ Fix tamamlandı.")


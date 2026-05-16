import paramiko

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Bağlandı")

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode().strip()
    print(f"  $ {cmd[:80]}")
    if out:
        print(f"  {out[:300]}")
    return out

# Container adı bul
container = run("docker ps --filter name=anamnezai-backend --format '{{.Names}}' | head -1")
print(f"\n  Container: {container}")

# /srv/anamnezai/frontend/ → container /app/frontend/ olarak volume mount yap YERİNE
# docker cp ile kopyala (hızlı yol)
print("\n📦 Font dosyaları container'a kopyalanıyor...")
run(f"docker cp /srv/anamnezai/frontend/vendor/fonts/. {container}:/app/frontend/vendor/fonts/", timeout=30)

# Doğrula
print("\n🔍 Container içi doğrulama:")
run(f"docker exec {container} ls /app/frontend/vendor/fonts/ | head -10")
run(f"docker exec {container} ls /app/frontend/vendor/fonts/ | wc -l")

# HTTP testi
print("\n🌐 HTTP testi:")
tests = [
    "/vendor/fonts/material_symbols_outlined.woff2",
    "/vendor/fonts/font_5.woff2",
    "/vendor/fonts/font_6.woff2",
    "/vendor/fonts/local_fonts.css",
    "/vendor/fonts/material_symbols_local.css",
]
for path in tests:
    code = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8001{path}")
    icon = "✅" if "200" in code else "❌"
    print(f"  {icon} {code}  {path}")

# Ayrıca docker-compose.yml'e volume mount ekle (kalıcı çözüm — rebuild olmadan)
print("\n🔧 docker-compose.yml'e frontend volume mount ekleniyor (kalıcı çözüm)...")
# backend volumes bölümüne frontend mount ekle
run(r"""sed -i '/chroma_data:\/app\/chroma_db/a\      # Frontend statik dosyaları (hot-reload)\n      - /srv/anamnezai/frontend:/app/frontend:ro' /srv/anamnezai/docker-compose.yml""")
run("cd /srv/anamnezai && docker compose up -d --no-recreate", timeout=60)

print("\n✅ Tamamlandı.")
client.close()


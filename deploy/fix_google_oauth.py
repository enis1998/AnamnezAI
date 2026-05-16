#!/usr/bin/env python3
"""Google OAuth Client ID'yi sunucuya yazar ve container'ı restart eder."""
import paramiko, sys, os

PASSWORD = sys.argv[1] if len(sys.argv) > 1 else "nWTGzzDqwyFyNJhqMhvcjEJj"
GOOGLE_CLIENT_ID = "201244506846-m28jucbi8roj6io5126pabv8bmfcu71o.apps.googleusercontent.com"

LOCAL_FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password=PASSWORD, timeout=15)

def run(cmd):
    _, stdout, stderr = client.exec_command(cmd, timeout=30)
    return (stdout.read() + stderr.read()).decode('utf-8', 'replace').strip()

print("=" * 60)
print("🔧 Google OAuth Fix")
print("=" * 60)

# 1. .env dosyasını güncelle
print("\n📝 1. Sunucu .env dosyası güncelleniyor...")
env_path = "/srv/anamnezai/.env"
existing = run(f"cat {env_path} 2>/dev/null || echo ''")

# GOOGLE_CLIENT_ID satırını güncelle veya ekle
if "GOOGLE_CLIENT_ID=" in existing:
    # Mevcut satırı güncelle
    new_env = "\n".join(
        f"GOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID}" if line.startswith("GOOGLE_CLIENT_ID=") else line
        for line in existing.split("\n")
    )
else:
    new_env = existing + f"\nGOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID}"

# Dosyaya yaz
run(f"cat > {env_path} << 'ENVEOF'\n{new_env}\nENVEOF")
print(f"  ✅ GOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID[:40]}...")

# 2. docker-compose.yml'i .env ile tekrar başlat (env inject)
print("\n🐳 2. Container env güncelleniyor...")
# Docker'ı --env-file ile restart etmek yerine direkt env set
r = run(f'docker exec anamnezai-backend-1 sh -c "export GOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID} && echo OK"')
# En güvenilir yöntem: container'ı .env dosyasıyla restart
r = run(f"cd /srv/anamnezai && GOOGLE_CLIENT_ID={GOOGLE_CLIENT_ID} docker compose up -d --no-deps backend 2>&1 | tail -5")
print(f"  {r}")

# 3. login.html güncelle
print("\n🌐 3. login.html sunucuya yükleniyor...")
sftp = client.open_sftp()
local_login = os.path.join(LOCAL_FRONTEND, "login.html")
sftp.put(local_login, "/srv/anamnezai/frontend/login.html")
print("  ✅ login.html yüklendi")

# 4. Docker cp
r = run("docker cp /srv/anamnezai/frontend/login.html anamnezai-backend-1:/app/frontend/login.html")
print(f"  ✅ login.html → container")
sftp.close()

# 5. Birkaç saniye bekle
import time
print("\n⏳ Container başlaması bekleniyor (10s)...")
time.sleep(10)

# 6. Doğrulama
print("\n🔍 4. Doğrulama...")
r = run("docker exec anamnezai-backend-1 env | grep GOOGLE_CLIENT")
print(f"  Backend env: {r}")

r = run('curl -s -X POST http://localhost:8001/auth/google -H "Content-Type: application/json" -d \'{"credential":"invalid_token"}\' 2>&1')
print(f"  Test endpoint: {r[:200]}")

# login.html Client ID kontrolü
r = run(f"grep -o 'GOOGLE_CLIENT_ID.*' /srv/anamnezai/frontend/login.html | head -1")
print(f"  Frontend: {r[:100]}")

client.close()
print("\n✅ Google OAuth fix tamamlandı!")
print(f"\n📋 Özet:")
print(f"  Client ID: {GOOGLE_CLIENT_ID}")
print(f"  Backend: GOOGLE_CLIENT_ID env ayarlandı")
print(f"  Frontend: login.html güncellendi")


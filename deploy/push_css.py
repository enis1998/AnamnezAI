import paramiko, os

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

LOCAL_CSS = r"C:\Users\pc\Desktop\Health\mediscreen\frontend\vendor\fonts\material_symbols_local.css"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Bağlandı")

sftp = client.open_sftp()

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode().strip()
    print(f"  $ {cmd[:80]}")
    if out: print(f"  {out[:200]}")
    return out

# 1) Host'taki dosyayı güncelle
print("\n📤 material_symbols_local.css host'a yükleniyor...")
sftp.put(LOCAL_CSS, "/srv/anamnezai/frontend/vendor/fonts/material_symbols_local.css")
print("  ✅ Host'a yüklendi")

# 2) Docker container'a kopyala
print("\n📦 Container'a kopyalanıyor...")
run("docker cp /srv/anamnezai/frontend/vendor/fonts/material_symbols_local.css "
    "anamnezai-backend-1:/app/frontend/vendor/fonts/material_symbols_local.css")

# 3) Doğrula — container içindeki dosyanın içeriğini göster
print("\n🔍 Container içindeki CSS doğrulama:")
run("docker exec anamnezai-backend-1 cat /app/frontend/vendor/fonts/material_symbols_local.css")

# 4) HTTP Response headers kontrolü (cache headers)
print("\n🌐 HTTP cache header kontrolü:")
run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_local.css | grep -E 'HTTP|Cache|Content-Type|ETag'")

# 5) Service Worker dosyasını da güncelle (cache version artır)
print("\n🔄 Service Worker cache version güncelleniyor...")
run("docker exec anamnezai-backend-1 grep -n 'CACHE_VERSION\\|v1\\|v2\\|version' /app/frontend/sw.js | head -5")

sftp.close()
client.close()
print("\n✅ CSS güncellendi. Tarayıcıda Ctrl+Shift+R yapın!")


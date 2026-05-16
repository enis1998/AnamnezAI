import paramiko, time

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

sftp = client.open_sftp()

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode().strip()
    print(f"  $ {cmd[:80]}")
    if out: print(f"  {out[:300]}")
    return out

# 1) main.py güncelle
print("📤 main.py yükleniyor...")
sftp.put(r"C:\Users\pc\Desktop\Health\mediscreen\backend\main.py",
         "/srv/anamnezai/backend/main.py")
run("docker cp /srv/anamnezai/backend/main.py anamnezai-backend-1:/app/main.py")
print("  ✅ main.py kopyalandı")

# 2) Backend restart
print("\n🔄 Backend yeniden başlatılıyor...")
run("docker restart anamnezai-backend-1", timeout=30)
time.sleep(12)

# 3) Healthcheck
print("\n🏥 Health check...")
out = run("curl -s --max-time 5 http://localhost:8001/healthz")
print(f"  healthz: {out}")

# 4) woff2 Content-Type kontrolü
print("\n🔍 woff2 Content-Type kontrolü:")
out = run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_outlined.woff2 | grep -E 'Content-Type|HTTP'")
print(f"  {out}")

# 5) CSS Content-Type kontrolü
out = run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_local.css | grep -E 'Content-Type|HTTP'")
print(f"  {out}")

# 6) Python MIME type doğrulama (container içinde)
print("\n🐍 Python MIME type doğrulama:")
run("docker exec anamnezai-backend-1 python3 -c \"import mimetypes; mimetypes.add_type('font/woff2','.woff2'); print(mimetypes.guess_type('test.woff2'))\"")

sftp.close()
client.close()
print("\n✅ Tamamlandı!")
print("   Tarayıcıda Ctrl+Shift+R (hard refresh) yapın.")
print("   Veya F12 → Application → Storage → Clear site data")


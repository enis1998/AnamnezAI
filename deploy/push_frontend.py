"""
Tüm frontend HTML, JS, JSON dosyalarını sunucuya push eder
ve volume mount üzerinden container'a ulaşmasını sağlar.
"""
import paramiko, os, time

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

LOCAL_FRONTEND = r"C:\Users\pc\Desktop\Health\mediscreen\frontend"
REMOTE_FRONTEND = "/srv/anamnezai/frontend"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

sftp = client.open_sftp()

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode().strip()
    print(f"  $ {cmd[:100]}")
    if out: print(f"  → {out[:400]}")
    return out

def sftp_put_file(local_path, remote_path):
    """Dosyayı SFTP ile yükle, gerekirse remote dir oluştur."""
    remote_dir = os.path.dirname(remote_path).replace("\\", "/")
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        # Dizin yoksa oluştur
        run(f"mkdir -p {remote_dir}")
    sftp.put(local_path, remote_path)

# Hangi uzantıları yükleyeceğiz (vendor klasörü hariç)
UPLOAD_EXTS = {'.html', '.js', '.json', '.css', '.py'}

print("=" * 60)
print("📤 Frontend dosyaları sunucuya yükleniyor...")
print("=" * 60)

uploaded = []
skipped = []

for root, dirs, files in os.walk(LOCAL_FRONTEND):
    # vendor klasörünü atla (font/lib dosyaları zaten yüklendi)
    dirs[:] = [d for d in dirs if d != 'vendor' and d != 'screens']

    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in UPLOAD_EXTS:
            skipped.append(fname)
            continue

        local_path = os.path.join(root, fname)
        # Relative path hesapla
        rel = os.path.relpath(local_path, LOCAL_FRONTEND).replace("\\", "/")
        remote_path = f"{REMOTE_FRONTEND}/{rel}"

        try:
            sftp_put_file(local_path, remote_path)
            print(f"  ✅ {rel}")
            uploaded.append(rel)
        except Exception as e:
            print(f"  ❌ {rel} → {e}")

print(f"\n📊 {len(uploaded)} dosya yüklendi, {len(skipped)} atlandı")

# sw.js cache versiyonunu kontrol et
print("\n🔍 sw.js cache versiyonu kontrol ediliyor...")
out = run(f"grep -o 'anamnezai-v[0-9]*' {REMOTE_FRONTEND}/sw.js || echo 'bulunamadı'")
print(f"  Cache version: {out}")

# Volume mount üzerinden container erişimini doğrula
print("\n🐳 Container'dan doctor.html erişim testi...")
out = run("docker exec anamnezai-backend-1 head -5 /app/frontend/doctor.html 2>&1 || echo 'HATA'")
print(f"  {out}")

# doctor.html içinde DL var mı kontrol et
print("\n🔍 doctor.html DL çeviri sistemi kontrolü:")
out = run(f"grep -c 'const DL' {REMOTE_FRONTEND}/doctor.html 2>/dev/null || echo '0'")
print(f"  'const DL' satır sayısı: {out}")

out = run(f"grep -c 'btnReport' {REMOTE_FRONTEND}/doctor.html 2>/dev/null || echo '0'")
print(f"  'btnReport' referans sayısı: {out}")

# Container versiyonu da kontrol et (volume mount varsa aynı olmalı)
print("\n🐳 Container içi doctor.html DL kontrolü:")
out = run("docker exec anamnezai-backend-1 grep -c 'const DL' /app/frontend/doctor.html 2>&1 || echo 'HATA'")
print(f"  Container 'const DL': {out}")

sftp.close()
client.close()

print("\n" + "=" * 60)
print("✅ Frontend push tamamlandı!")
print("   Tarayıcıda Ctrl+Shift+R (hard refresh) yapın.")
print("   Veya F12 → Application → Storage → Clear site data")
print("=" * 60)


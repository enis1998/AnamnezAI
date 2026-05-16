import paramiko
import os

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

LOCAL_FRONTEND = r"C:\Users\pc\Desktop\Health\mediscreen\frontend"
REMOTE_FRONTEND = "/srv/anamnezai/frontend"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Bağlandı")

sftp = client.open_sftp()

def ensure_remote_dir(path):
    try:
        sftp.stat(path)
    except:
        sftp.mkdir(path)

# Tüm eksik dosya uzantılarını yükle
EXTRA_EXTENSIONS = {'.woff2', '.woff', '.ttf', '.eot', '.otf', '.ico', '.png', '.svg', '.webp', '.jpg', '.gif', '.mp4'}

uploaded = 0
skipped = 0
errors = 0

for root_dir, dirs, files in os.walk(LOCAL_FRONTEND):
    # __pycache__ atla
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]

    rel = os.path.relpath(root_dir, LOCAL_FRONTEND).replace('\\', '/')
    remote_dir = REMOTE_FRONTEND if rel == '.' else f"{REMOTE_FRONTEND}/{rel}"

    # Remote dizini oluştur
    ensure_remote_dir(remote_dir)

    for fn in files:
        ext = os.path.splitext(fn)[1].lower()
        if ext not in EXTRA_EXTENSIONS:
            continue

        local_path = os.path.join(root_dir, fn)
        remote_path = f"{remote_dir}/{fn}"

        # Zaten var mı kontrol et
        try:
            remote_stat = sftp.stat(remote_path)
            local_size = os.path.getsize(local_path)
            if remote_stat.st_size == local_size:
                skipped += 1
                continue
        except:
            pass  # dosya yok, yükle

        try:
            sftp.put(local_path, remote_path)
            size_kb = os.path.getsize(local_path) / 1024
            print(f"  ✅ {rel}/{fn} ({size_kb:.0f} KB)")
            uploaded += 1
        except Exception as e:
            print(f"  ❌ {rel}/{fn} → {e}")
            errors += 1

sftp.close()
client.close()

print(f"\n{'='*50}")
print(f"Yüklendi: {uploaded} | Atlandı (zaten var): {skipped} | Hata: {errors}")
print("✅ Font ve ikon dosyaları tamamlandı.")


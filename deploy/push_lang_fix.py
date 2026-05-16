#!/usr/bin/env python3
"""Dil butonu aktif durum fix'ini canlı sunucuya gönderir."""
import paramiko, os, sys

HOST = "10.200.9.11"
PORT = 22
USER = "root"
REMOTE_DIR = "/srv/anamnezai/frontend"
CONTAINER = "anamnezai-backend-1"
CONTAINER_DIR = "/app/frontend"

LOCAL_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

FILES = [
    "doctor.html",
    "admin.html",
    "index.html",
    "patient_dashboard.html",
]

def get_password():
    if len(sys.argv) > 1:
        return sys.argv[1]
    import getpass
    return getpass.getpass(f"SSH password for {USER}@{HOST}: ")

def main():
    password = get_password()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"🔗 {HOST}:{PORT} bağlanıyor...")
    ssh.connect(HOST, port=PORT, username=USER, password=password, timeout=30)
    sftp = ssh.open_sftp()

    print(f"\n{'='*60}")
    print(f"🌐 Dil butonu fix dosyaları yükleniyor...")
    print(f"{'='*60}")

    ok, skip = 0, 0
    for fname in FILES:
        local_path = os.path.join(LOCAL_DIR, fname)
        if not os.path.isfile(local_path):
            print(f"  ⚠️  {fname} — BULUNAMADI")
            skip += 1
            continue
        remote_path = f"{REMOTE_DIR}/{fname}"
        sftp.put(local_path, remote_path)
        print(f"  ✅  {fname}")
        ok += 1

    sftp.close()
    print(f"\n📦 {ok} dosya yüklendi, {skip} atlandı")

    # Docker container'a kopyala
    print("\n🐳 Docker container'a kopyalanıyor...")
    for fname in FILES:
        local_path = os.path.join(LOCAL_DIR, fname)
        if not os.path.isfile(local_path):
            continue
        remote_path = f"{REMOTE_DIR}/{fname}"
        cmd = f"docker cp {remote_path} {CONTAINER}:{CONTAINER_DIR}/{fname}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        err = stderr.read().decode().strip()
        if exit_code == 0:
            print(f"  ✅  {fname} → container")
        else:
            print(f"  ❌  {fname} — {err}")

    # Nginx reload
    print("\n🔄 Nginx reload...")
    _, out, err = ssh.exec_command("nginx -s reload 2>&1 || systemctl reload nginx 2>&1")
    print("  ", out.read().decode().strip() or "OK")

    # Doğrulama
    print("\n🔍 Doğrulama...")
    for fname in ["doctor.html", "admin.html", "index.html"]:
        cmd = f"grep -c 'el.style.background' {REMOTE_DIR}/{fname} 2>/dev/null || echo 0"
        _, out, _ = ssh.exec_command(cmd)
        count = out.read().decode().strip()
        status = "✅" if int(count) > 0 else "❌"
        print(f"  {status}  {fname} — lang style fix: {count} yer")

    ssh.close()
    print("\n✅ Deploy tamamlandı!")

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Push UI polish fixes: admin, summary, clinical_review, doctor HTML"""
import paramiko, time

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"
LOCAL = r"C:\Users\pc\Desktop\Health\mediscreen"
REMOTE = "/srv/anamnezai"
CONTAINER = "anamnezai-backend-1"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)

sftp = client.open_sftp()

def run(cmd, timeout=30):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode('utf-8', errors='replace').strip()
    print(f"  $ {cmd[:80]}")
    if out: print(f"    {out[:200]}")
    return out

def push(local_rel, remote_rel):
    import os
    lp = os.path.join(LOCAL, local_rel)
    rp = f"{REMOTE}/{remote_rel}"
    sftp.put(lp, rp)
    print(f"  ✅ {local_rel}")

print("📤 UI polish dosyaları yükleniyor...")
push("frontend/admin.html",          "frontend/admin.html")
push("frontend/summary.html",        "frontend/summary.html")
push("frontend/clinical_review.html","frontend/clinical_review.html")
push("frontend/doctor.html",         "frontend/doctor.html")

print("\n🐳 Container'a kopyalanıyor...")
run(f"docker cp {REMOTE}/frontend/admin.html {CONTAINER}:/app/frontend/admin.html")
run(f"docker cp {REMOTE}/frontend/summary.html {CONTAINER}:/app/frontend/summary.html")
run(f"docker cp {REMOTE}/frontend/clinical_review.html {CONTAINER}:/app/frontend/clinical_review.html")
run(f"docker cp {REMOTE}/frontend/doctor.html {CONTAINER}:/app/frontend/doctor.html")

sftp.close()
client.close()
print("\n✅ UI polish push tamamlandı!")
print("   (Backend restart gerekmiyor — sadece statik HTML değişti)")


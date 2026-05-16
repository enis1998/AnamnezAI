#!/usr/bin/env python3
"""final_push.py — Son push: sw.js + favicon.ico + robots.txt"""
import paramiko, os

HOST      = "10.200.9.11"
USER      = "root"
PASS      = "nWTGzzDqwyFyNJhqMhvcjEJj"
LOCAL     = r"C:\Users\pc\Desktop\Health\mediscreen"
REMOTE    = "/srv/anamnezai"
CONTAINER = "anamnezai-backend-1"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)
sftp = client.open_sftp()

def run(cmd, timeout=30):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace').strip()
    err = stderr.read().decode('utf-8', 'replace').strip()
    return out or err

def push(local_rel, remote_rel):
    lp = os.path.join(LOCAL, local_rel)
    rp = f"{REMOTE}/{remote_rel}"
    sftp.put(lp, rp)
    print(f"  ✅ {local_rel}")

print("📤 Son dosyalar yükleniyor...")
push("frontend/sw.js",       "frontend/sw.js")
push("frontend/favicon.ico", "frontend/favicon.ico")
push("frontend/robots.txt",  "frontend/robots.txt")
push("frontend/sitemap.xml", "frontend/sitemap.xml")

print("\n🐳 Container'a kopyalanıyor...")
run(f"docker cp {REMOTE}/frontend/sw.js {CONTAINER}:/app/frontend/sw.js")
run(f"docker cp {REMOTE}/frontend/favicon.ico {CONTAINER}:/app/frontend/favicon.ico")
run(f"docker cp {REMOTE}/frontend/robots.txt {CONTAINER}:/app/frontend/robots.txt")
run(f"docker cp {REMOTE}/frontend/sitemap.xml {CONTAINER}:/app/frontend/sitemap.xml")

print("\n🔍 Doğrulama:")
BASE = "http://localhost:8001"
checks = [
    ("/favicon.ico", "200"),
    ("/robots.txt",  "200"),
    ("/sitemap.xml", "200"),
    ("/sw.js",       "200"),
]
for path, expected in checks:
    code = run(f"curl -sI --max-time 3 '{BASE}{path}' | head -1")
    ok = expected in code
    print(f"  {'✅' if ok else '❌'} {path}: {code[:30]}")

# SW versiyonu kontrol
sw_ver = run(f"grep 'CACHE_NAME' {REMOTE}/frontend/sw.js")
print(f"\n  SW Versiyon: {sw_ver}")

sftp.close()
client.close()
print("\n✅ Son push tamamlandı!")


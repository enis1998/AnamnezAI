#!/usr/bin/env python3
"""
push_final_qa.py
Tüm QA düzeltmelerini canlıya gönderir:
  - backend: main.py, rag.py, database.py, tests/test_smoke.py
  - frontend: admin.html, doctor.html, landing.html, summary.html, sw.js
Ardından backend'i yeniden başlatır ve health-check yapar.
"""
import paramiko, time, os

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
print("✅ SSH bağlantısı kuruldu")

sftp = client.open_sftp()

def run(cmd, timeout=60, ignore_err=False):
    print(f"  $ {cmd[:90]}{'...' if len(cmd)>90 else ''}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    rc  = stdout.channel.recv_exit_status()
    if out: print(f"    {out[:300]}")
    if err and not ignore_err: print(f"    [err] {err[:200]}")
    return out, err, rc

def push(local_rel, remote_rel):
    lp = os.path.join(LOCAL, local_rel)
    rp = f"{REMOTE}/{remote_rel}"
    try:
        sftp.put(lp, rp)
        print(f"  ✅ {local_rel}")
    except Exception as e:
        print(f"  ❌ {local_rel}: {e}")
        raise

# ── 1. Backend Python dosyaları ──────────────────────────────────────────────
print("\n📤 Backend dosyaları yükleniyor...")
push("backend/main.py",              "backend/main.py")
push("backend/rag.py",               "backend/rag.py")
push("backend/database.py",          "backend/database.py")
push("backend/auth.py",              "backend/auth.py")
push("backend/safety.py",            "backend/safety.py")
push("backend/requirements.txt",     "backend/requirements.txt")

# ── 2. Frontend dosyaları ─────────────────────────────────────────────────────
print("\n📤 Frontend dosyaları yükleniyor...")
push("frontend/landing.html",        "frontend/landing.html")
push("frontend/admin.html",          "frontend/admin.html")
push("frontend/doctor.html",         "frontend/doctor.html")
push("frontend/summary.html",        "frontend/summary.html")
push("frontend/sw.js",               "frontend/sw.js")
# Diğer kritik sayfalar
for page in ["index.html","login.html","register.html","kiosk.html",
             "previsit.html","patient_dashboard.html","clinical_review.html",
             "evaluation.html","profile.html","analytics.html"]:
    lp = os.path.join(LOCAL, "frontend", page)
    if os.path.exists(lp):
        push(f"frontend/{page}", f"frontend/{page}")

# ── 3. Backend container'a dosyaları kopyala ─────────────────────────────────
print("\n🐳 Container'a dosyalar kopyalanıyor...")
for f in ["main.py","rag.py","database.py","auth.py","safety.py"]:
    run(f"docker cp {REMOTE}/backend/{f} {CONTAINER}:/app/{f}")

# ── 4. Service Worker güncelleme: SW cache temizle ───────────────────────────
print("\n🔄 Frontend güncelleniyor (container)...")
run(f"docker cp {REMOTE}/frontend/. {CONTAINER}:/app/frontend/")

# ── 5. Backend yeniden başlat ─────────────────────────────────────────────────
print("\n🔄 Backend yeniden başlatılıyor...")
run(f"docker restart {CONTAINER}", timeout=40)
print("  Başlangıç bekleniyor (15s)...")
time.sleep(15)

# ── 6. Health check ───────────────────────────────────────────────────────────
print("\n🏥 Health check...")
out, _, rc = run("curl -s --max-time 8 http://localhost:8001/healthz")
if rc == 0 and out:
    print(f"  healthz: {out[:200]}")
else:
    print("  ⚠️  healthz yanıt vermedi — container başlıyor olabilir")
    time.sleep(10)
    out, _, _ = run("curl -s --max-time 8 http://localhost:8001/healthz")
    print(f"  healthz (2.deneme): {out[:200]}")

# ── 7. Endpoint doğrulama ─────────────────────────────────────────────────────
print("\n🔍 Endpoint doğrulaması...")
for endpoint in ["/api/public/landing-metrics", "/api/demo/cases"]:
    out, _, rc = run(f"curl -s --max-time 5 http://localhost:8001{endpoint}")
    status = "✅" if (rc==0 and out) else "⚠️"
    print(f"  {status} {endpoint}: {out[:80]}")

# ── 8. nginx / proxy durumu ───────────────────────────────────────────────────
print("\n🌐 nginx proxy durumu...")
run("nginx -t 2>&1", ignore_err=True)
run("systemctl is-active nginx", ignore_err=True)
out, _, _ = run("curl -sI --max-time 5 https://lifetrack.com.tr/ | head -3", ignore_err=True)
print(f"  lifetrack.com.tr: {out[:200]}")

sftp.close()
client.close()

print("\n" + "="*60)
print("✅ Deployment tamamlandı!")
print("   Tarayıcıda Ctrl+Shift+R (hard refresh) yapın")
print("   Service Worker cache temizlemek için:")
print("   F12 → Application → Storage → Clear site data")
print("="*60)


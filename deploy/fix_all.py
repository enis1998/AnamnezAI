#!/usr/bin/env python3
"""
fix_all.py — Tüm eksiklikleri düzelt:
1. gemma4:e4b model pull başlat
2. robots.txt oluştur
3. Warmup endpoint'i çağır
4. Tüm dosyaları senkronize et
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
sftp = client.open_sftp()

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(f"  $ {cmd[:90]}")
    if out: print(f"    OUT: {out[:300]}")
    if err: print(f"    ERR: {err[:200]}")
    return out

def push(local_rel, remote_rel):
    lp = os.path.join(LOCAL, local_rel)
    rp = f"{REMOTE}/{remote_rel}"
    sftp.put(lp, rp)
    print(f"  ✅ {local_rel}")

print("=" * 65)
print("🔧 AnamnezAI — Eksiklik Düzeltme Scripti")
print("=" * 65)

# ── 1. Mevcut Ollama model listesini göster ──────────────────────────────
print("\n📊 1. Mevcut Ollama modelleri:")
run("ollama list 2>&1 | head -20")

# ── 2. gemma4:e4b model pull ─────────────────────────────────────────────
print("\n⬇️  2. gemma4:e4b model pull başlatılıyor (arka planda)...")
print("   NOT: Bu işlem ~9.6 GB indirir, 10-30 dakika sürebilir")
# Pull'u arka planda başlat
_, stdout, _ = client.exec_command(
    "nohup ollama pull gemma4:e4b > /var/log/ollama_pull.log 2>&1 & echo $!",
    timeout=10
)
pid = stdout.read().decode().strip()
print(f"  Pull PID: {pid}")
print(f"  Log: /var/log/ollama_pull.log")

# İlerlemeyi biraz bekle
time.sleep(5)
run("tail -3 /var/log/ollama_pull.log 2>/dev/null || echo 'Log henüz yok'")

# ── 3. robots.txt oluştur ────────────────────────────────────────────────
print("\n📄 3. robots.txt oluşturuluyor...")
robots_content = """User-agent: *
Allow: /
Allow: /landing.html
Allow: /index.html
Allow: /doctor.html
Allow: /kiosk.html
Allow: /admin.html
Allow: /api/public/

Disallow: /api/session/
Disallow: /api/admin/
Disallow: /api/patients/
Disallow: /api/audit/
Disallow: /*.log$

Sitemap: https://lifetrack.com.tr/sitemap.xml
"""

# Lokal robots.txt yaz
robots_local = os.path.join(LOCAL, "frontend", "robots.txt")
with open(robots_local, "w") as f:
    f.write(robots_content)
print(f"  Lokal yazıldı: {robots_local}")

push("frontend/robots.txt", "frontend/robots.txt")
run(f"docker cp {REMOTE}/frontend/robots.txt {CONTAINER}:/app/frontend/robots.txt")
run(f"curl -sI --max-time 3 http://localhost:8001/robots.txt | head -1")

# ── 4. sitemap.xml oluştur ───────────────────────────────────────────────
print("\n🗺️  4. sitemap.xml oluşturuluyor...")
sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://lifetrack.com.tr/landing.html</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://lifetrack.com.tr/index.html</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
  <url><loc>https://lifetrack.com.tr/login.html</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://lifetrack.com.tr/register.html</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://lifetrack.com.tr/kiosk.html</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
</urlset>
"""
sitemap_local = os.path.join(LOCAL, "frontend", "sitemap.xml")
with open(sitemap_local, "w") as f:
    f.write(sitemap_content)
push("frontend/sitemap.xml", "frontend/sitemap.xml")
run(f"docker cp {REMOTE}/frontend/sitemap.xml {CONTAINER}:/app/frontend/sitemap.xml")

# ── 5. favicon.ico oluştur (minimal) ─────────────────────────────────────
print("\n🎯 5. favicon.ico redirect kontrolü...")
favicon_check = run("curl -sI --max-time 3 http://localhost:8001/favicon.ico | head -1")
print(f"   favicon mevcut: {favicon_check}")

# ── 6. Tüm frontend dosyaları senkronize et ──────────────────────────────
print("\n📤 6. Frontend dosyaları güncelleniyor...")
frontend_files = [
    "landing.html", "index.html", "login.html", "register.html",
    "doctor.html", "admin.html", "kiosk.html", "summary.html",
    "clinical_review.html", "previsit.html", "patient_dashboard.html",
    "profile.html", "analytics.html", "evaluation.html",
    "channel_demo.html", "sw.js", "manifest.json", "version.json",
    "robots.txt", "sitemap.xml"
]
for fname in frontend_files:
    lp = os.path.join(LOCAL, "frontend", fname)
    if os.path.exists(lp):
        push(f"frontend/{fname}", f"frontend/{fname}")

run(f"docker cp {REMOTE}/frontend/. {CONTAINER}:/app/frontend/")

# ── 7. Backend dosyaları senkronize et ───────────────────────────────────
print("\n📤 7. Backend dosyaları güncelleniyor...")
for bfile in ["main.py", "rag.py", "database.py", "auth.py", "safety.py"]:
    push(f"backend/{bfile}", f"backend/{bfile}")
    run(f"docker cp {REMOTE}/backend/{bfile} {CONTAINER}:/app/{bfile}")

# ── 8. Backend restart ────────────────────────────────────────────────────
print("\n🔄 8. Backend yeniden başlatılıyor...")
run(f"docker restart {CONTAINER}", timeout=45)
print("   15 saniye bekleniyor...")
time.sleep(15)

# ── 9. Doğrulama ─────────────────────────────────────────────────────────
print("\n✅ 9. Doğrulama:")
check_endpoints = [
    "/healthz",
    "/api/public/landing-metrics",
    "/api/demo/cases",
    "/api/offline-proof",
    "/api/evaluation",
    "/robots.txt",
    "/sitemap.xml",
]
for ep in check_endpoints:
    out = run(f"curl -s --max-time 5 http://localhost:8001{ep} | head -c 80")
    ok = len(out) > 5 and 'Not Found' not in out and '404' not in out
    print(f"  {'✅' if ok else '❌'} {ep}: {out[:70]}")

# ── 10. Ollama model pull durumu ─────────────────────────────────────────
print("\n⬇️  10. Ollama pull durumu:")
run("tail -5 /var/log/ollama_pull.log 2>/dev/null || echo 'Henüz başlamadı'")
run("ollama list 2>&1")

sftp.close()
client.close()

print("\n" + "=" * 65)
print("✅ Düzeltme scripti tamamlandı!")
print("   Model indirme devam ediyor — /var/log/ollama_pull.log takip edin")
print("   Model hazır olduğunda tüm AI özellikler çalışacak")
print("=" * 65)


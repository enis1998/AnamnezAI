#!/usr/bin/env python3
"""
quick_qa.py  — Canlı site hızlı QA check
- nginx proxy config doğrulama
- Kritik endpoint'leri test et
- Temel HTML sayfalarının erişilebilirliğini kontrol et
"""
import paramiko, json, time

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out or err

def check(label, url, expect=None):
    out = run(f"curl -s --max-time 5 '{url}'")
    ok = (expect in out) if expect else bool(out and len(out) > 20)
    status = "✅" if ok else "❌"
    print(f"  {status} {label}: {out[:80]}")
    return ok

def check_http(label, url, expect_status="200"):
    out = run(f"curl -sI --max-time 5 '{url}' | head -1")
    ok = expect_status in out
    status = "✅" if ok else "❌"
    print(f"  {status} {label}: {out[:60]}")
    return ok

print("=" * 60)
print("🔍 AnamnezAI Canlı QA Check")
print("=" * 60)

# ── nginx config ──────────────────────────────────────────────
print("\n📋 nginx proxy config:")
out = run("cat /etc/nginx/sites-enabled/*.conf 2>/dev/null || cat /etc/nginx/sites-enabled/default 2>/dev/null || cat /etc/nginx/conf.d/*.conf 2>/dev/null")
if out:
    print(out[:1500])
else:
    print("  Config file bulunamadı — nginx.conf içinde location bloğu:")
    out2 = run("grep -A10 'proxy_pass' /etc/nginx/nginx.conf | head -30")
    print(out2[:800])

# ── Backend health endpoint'leri ─────────────────────────────
print("\n🏥 Backend endpoints (localhost:8001):")
check("/healthz", "http://localhost:8001/healthz", '"status":"ok"')
check("/api/public/landing-metrics", "http://localhost:8001/api/public/landing-metrics", '"source"')
check("/api/demo/cases", "http://localhost:8001/api/demo/cases", '"cases"')
check("/api/offline-proof", "http://localhost:8001/api/offline-proof", '"strict_local_mode"')

# ── Frontend sayfaları (frontend dizini) ─────────────────────
print("\n📄 Frontend dosya varlığı:")
for page in ["index.html","landing.html","login.html","doctor.html","admin.html",
             "kiosk.html","summary.html","clinical_review.html","previsit.html"]:
    out = run(f"test -f /srv/anamnezai/frontend/{page} && echo EXISTS || echo MISSING")
    status = "✅" if "EXISTS" in out else "❌"
    print(f"  {status} {page}")

# ── sw.js cache versiyonu ─────────────────────────────────────
print("\n🔧 Service Worker versiyonu:")
out = run("grep -E 'CACHE_NAME|APP_VERSION' /srv/anamnezai/frontend/sw.js")
print(f"  {out}")

# ── ALLOW_CLOUD_TRANSLATION kontrolü ─────────────────────────
print("\n🔒 Privacy ayarları:")
out = run("grep -n 'ALLOW_CLOUD_TRANSLATION' /srv/anamnezai/backend/rag.py | head -5")
print(f"  rag.py: {out[:200]}")
out2 = run("grep -n 'strict_local_mode' /srv/anamnezai/backend/main.py | head -3")
print(f"  main.py: {out2[:200]}")

# ── Demo endpoint sonuç sayısı ────────────────────────────────
print("\n📊 Demo case sayısı:")
out = run("curl -s --max-time 5 http://localhost:8001/api/demo/cases")
try:
    d = json.loads(out)
    print(f"  Demo cases: {len(d.get('cases', []))} adet")
except:
    print(f"  Parse hatası: {out[:100]}")

# ── Container durumu ──────────────────────────────────────────
print("\n🐳 Container durumu:")
out = run("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAME|anamnezai'")
print(f"  {out[:400]}")

client.close()
print("\n✅ QA check tamamlandı!")


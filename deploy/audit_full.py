#!/usr/bin/env python3
"""
audit_full.py — Kapsamlı eksiklik tespiti
"""
import paramiko, os, json, re

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

def run(cmd, timeout=20):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out or err

print("=" * 70)
print("🔍 AnamnezAI — Tam Eksiklik Denetimi")
print("=" * 70)

# ── 1. HTTP erişimi — tüm kritik sayfalar ────────────────────────────────
print("\n📄 1. Kritik Sayfa HTTP Erişimi (HTTPS üzerinden):")
pages = [
    "/", "/landing.html", "/index.html", "/login.html", "/register.html",
    "/doctor.html", "/admin.html", "/kiosk.html", "/summary.html",
    "/clinical_review.html", "/previsit.html", "/patient_dashboard.html",
    "/profile.html", "/analytics.html", "/evaluation.html"
]
for page in pages:
    code = run(f"curl -sI --max-time 5 'https://lifetrack.com.tr{page}' | head -1")
    ok = "200" in code or "301" in code or "302" in code
    print(f"  {'✅' if ok else '❌'} {page:40s} {code[:40]}")

# ── 2. API endpoint'leri ─────────────────────────────────────────────────
print("\n🔌 2. API Endpoint'leri:")
api_tests = [
    ("/healthz",                      '"status":"ok"'),
    ("/health",                       '"status"'),
    ("/api/public/landing-metrics",   '"triage_accuracy_pct"'),
    ("/api/demo/cases",               '"cases"'),
    ("/api/offline-proof",            '"strict_local_mode"'),
    ("/api/session/start",            None),
    ("/docs",                         "swagger"),
]
for ep, expect in api_tests:
    out = run(f"curl -s --max-time 5 'https://lifetrack.com.tr{ep}'")
    if expect:
        ok = expect.lower() in out.lower()
    else:
        ok = len(out) > 0
    print(f"  {'✅' if ok else '❌'} {ep:45s} {out[:60]}")

# ── 3. Vendor / font dosyaları ───────────────────────────────────────────
print("\n📦 3. Vendor/Font Dosyası HTTP Testi:")
vendor_files = [
    "/vendor/tailwind.min.js",
    "/vendor/chart.umd.min.js",
    "/vendor/jspdf.umd.min.js",
    "/vendor/html2canvas.min.js",
    "/vendor/fonts/local_fonts.css",
    "/vendor/fonts/material_symbols.css",
    "/vendor/fonts/material_symbols_local.css",
    "/vendor/fonts/googlefonts_manrope_inter.css",
]
for vf in vendor_files:
    code = run(f"curl -sI --max-time 5 'https://lifetrack.com.tr{vf}' | head -1")
    ok = "200" in code
    print(f"  {'✅' if ok else '❌'} {vf:50s} {code[:30]}")

# ── 4. HTML içinde kırık referanslar tespit ───────────────────────────────
print("\n🔗 4. HTML Vendor Referans Denetimi (sunucu dosyaları):")
html_files = ["landing.html","index.html","doctor.html","admin.html",
              "summary.html","kiosk.html","login.html","register.html",
              "previsit.html","patient_dashboard.html","clinical_review.html"]
for hf in html_files:
    refs = run(f"grep -oE 'vendor/[^\"]+' /srv/anamnezai/frontend/{hf} 2>/dev/null | sort -u")
    if refs:
        lines = refs.split('\n')
        for ref in lines:
            ref = ref.strip()
            if not ref:
                continue
            code = run(f"curl -sI --max-time 3 'https://lifetrack.com.tr/{ref}' | head -1")
            ok = "200" in code
            if not ok:
                print(f"  ❌ {hf}: /{ref} → {code[:30]}")

# ── 5. Service Worker cache ──────────────────────────────────────────────
print("\n🔧 5. Service Worker:")
sw_ver   = run("grep -E 'CACHE_NAME|APP_VERSION' /srv/anamnezai/frontend/sw.js | head -3")
print(f"  {sw_ver}")

# ── 6. Backend container loglarında ERROR ────────────────────────────────
print("\n🐳 6. Backend Hata Logları (son 30):")
logs = run(f"docker logs {CONTAINER} --tail 30 2>&1 | grep -iE 'error|exception|traceback|failed' | head -20")
if logs:
    print(logs)
else:
    print("  ✅ Hata yok")

# ── 7. Lokal vs sunucu dosya karşılaştırması (kritik dosyalar) ───────────
print("\n📊 7. Lokal vs Sunucu Dosya Boyut Karşılaştırması:")
critical = [
    ("backend/main.py",     "backend/main.py"),
    ("frontend/landing.html","frontend/landing.html"),
    ("frontend/doctor.html", "frontend/doctor.html"),
    ("frontend/admin.html",  "frontend/admin.html"),
    ("frontend/sw.js",       "frontend/sw.js"),
]
for local_rel, remote_rel in critical:
    local_path = os.path.join(LOCAL, local_rel)
    remote_path = f"{REMOTE}/{remote_rel}"
    local_size = os.path.getsize(local_path) if os.path.exists(local_path) else -1
    remote_size_raw = run(f"wc -c < {remote_path} 2>/dev/null || echo 0")
    try:
        remote_size = int(remote_size_raw.strip())
    except:
        remote_size = -1
    match = "✅" if abs(local_size - remote_size) < 100 else "⚠️ "
    print(f"  {match} {local_rel:40s} local={local_size:8d}  remote={remote_size:8d}")

# ── 8. Ana özellik kontrolleri ───────────────────────────────────────────
print("\n🧪 8. Özellik Kontrolleri:")

# Demo oturumu başlatılabilir mi?
out = run("curl -s --max-time 8 -X POST 'https://lifetrack.com.tr/api/session/start' -H 'Content-Type: application/json' -d '{\"language\":\"tr\"}'")
has_session = "session_id" in out or "question" in out
print(f"  {'✅' if has_session else '❌'} POST /api/session/start: {out[:80]}")

# Hasta kuyruğu (demo token ile)
out2 = run("curl -s --max-time 5 'https://lifetrack.com.tr/api/patients/queue'")
print(f"  {'✅' if out2 else '❌'} GET /api/patients/queue: {out2[:60]}")

# Evaluation endpoint
out3 = run("curl -s --max-time 5 'https://lifetrack.com.tr/api/evaluation/results'")
print(f"  {'✅' if out3 else '❌'} GET /api/evaluation/results: {out3[:60]}")

client.close()

print("\n" + "=" * 70)
print("✅ Denetim tamamlandı!")
print("=" * 70)


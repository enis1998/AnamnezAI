#!/usr/bin/env python3
"""
audit_v2.py — localhost üzerinden kapsamlı denetim
"""
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

def run(cmd, timeout=20):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out or err

BASE = "http://localhost:8001"

print("=" * 70)
print("AnamnezAI — Eksiklik Denetimi (localhost)")
print("=" * 70)

# ── 1. Temel API'ler ─────────────────────────────────────────────────────
print("\n1. Temel API Kontrolleri:")
tests = [
    ("/healthz",                   '"status":"ok"'),
    ("/health",                    '"ollama"'),
    ("/api/public/landing-metrics",'"triage_accuracy_pct"'),
    ("/api/demo/cases",            '"cases"'),
    ("/api/offline-proof",         '"strict_local_mode"'),
    ("/api/evaluation/results",    '"accuracy"'),
    ("/api/evaluation/results",    '"cases"'),
    ("/docs",                      "swagger"),
]
for ep, expect in tests:
    out = run(f"curl -s --max-time 8 '{BASE}{ep}'")
    ok = expect.lower() in out.lower()
    print(f"  {'OK' if ok else 'EKSIK'} {ep:45s} {out[:80]}")

# ── 2. Session akışı testi ───────────────────────────────────────────────
print("\n2. Session Akış Testi:")
sess = run(f"curl -s --max-time 10 -X POST '{BASE}/api/session/start' -H 'Content-Type: application/json' -d '{{\"language\":\"tr\"}}'")
print(f"  session/start: {sess[:150]}")

import json
try:
    data = json.loads(sess)
    sid = data.get("session_id") or data.get("id")
    if sid:
        print(f"  Session ID: {sid}")
        ans = run(f"curl -s --max-time 8 -X POST '{BASE}/api/session/answer' -H 'Content-Type: application/json' -d '{{\"session_id\":\"{sid}\",\"answer\":\"bas agrim var\"}}'")
        print(f"  session/answer: {ans[:120]}")
    else:
        print("  HATA: session_id yok!")
except Exception as e:
    print(f"  JSON parse hatasi: {e}")

# ── 3. Doctor panel API'leri ─────────────────────────────────────────────
print("\n3. Doctor Panel API:")
q = run(f"curl -s --max-time 5 '{BASE}/api/patients/queue'")
print(f"  /api/patients/queue: {q[:100]}")

# ── 4. Vendor/font dosyaları (container içi) ─────────────────────────────
print("\n4. Vendor/Font Dosyalari (container icinde):")
vendor_files = [
    "/app/frontend/vendor/tailwind.min.js",
    "/app/frontend/vendor/chart.umd.min.js",
    "/app/frontend/vendor/fonts/local_fonts.css",
    "/app/frontend/vendor/fonts/material_symbols_local.css",
    "/app/frontend/vendor/fonts/googlefonts_manrope_inter.css",
]
for vf in vendor_files:
    exists = run(f"docker exec {CONTAINER} test -f {vf} && echo EXISTS || echo MISSING")
    print(f"  {'OK' if 'EXISTS' in exists else 'EKSIK'} {vf}")

# ── 5. HTTP erişim (localhost 8001) ──────────────────────────────────────
print("\n5. Vendor HTTP Erisimi (localhost:8001):")
vendor_http = [
    "/vendor/tailwind.min.js",
    "/vendor/chart.umd.min.js",
    "/vendor/fonts/local_fonts.css",
    "/vendor/fonts/material_symbols_local.css",
    "/vendor/fonts/material_symbols.css",
    "/vendor/fonts/googlefonts_manrope_inter.css",
]
for vf in vendor_http:
    code = run(f"curl -sI --max-time 5 '{BASE}{vf}' | head -1")
    print(f"  {'OK' if '200' in code else 'EKSIK'} {code[:10]} {vf}")

# ── 6. nginx SSL durumu ──────────────────────────────────────────────────
print("\n6. nginx SSL Durumu:")
ssl_test = run("curl -sI --max-time 5 'https://lifetrack.com.tr/health' 2>&1 | head -3")
print(f"  {ssl_test[:200]}")
nginx_status = run("systemctl is-active nginx")
print(f"  nginx: {nginx_status}")
cert = run("certbot certificates 2>/dev/null | grep -A3 'lifetrack.com.tr' | head -5")
print(f"  Sertifika: {cert}")

# ── 7. Sunucu vs Local fark analizi ─────────────────────────────────────
print("\n7. Kritik Dosya Fark Analizi:")
for local_rel, remote_rel in [
    ("backend/main.py",          "backend/main.py"),
    ("frontend/landing.html",    "frontend/landing.html"),
    ("frontend/doctor.html",     "frontend/doctor.html"),
    ("frontend/index.html",      "frontend/index.html"),
    ("frontend/admin.html",      "frontend/admin.html"),
    ("frontend/sw.js",           "frontend/sw.js"),
    ("frontend/login.html",      "frontend/login.html"),
    ("frontend/kiosk.html",      "frontend/kiosk.html"),
    ("frontend/summary.html",    "frontend/summary.html"),
]:
    lp = os.path.join(LOCAL, local_rel)
    rp = f"{REMOTE}/{remote_rel}"
    local_size = os.path.getsize(lp) if os.path.exists(lp) else -1
    remote_size_raw = run(f"wc -c < {rp} 2>/dev/null")
    try:
        remote_size = int(remote_size_raw.strip())
    except:
        remote_size = -1
    diff = abs(local_size - remote_size)
    status = "SYNC" if diff < 50 else f"FARK:{diff}"
    print(f"  {status:12s} {local_rel}")

# ── 8. Çalışan process'ler ───────────────────────────────────────────────
print("\n8. Canlı Processler:")
procs = run("docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'NAME|anamnez|postgres|nginx'")
print(f"  {procs}")

# ── 9. Son hata logları ──────────────────────────────────────────────────
print("\n9. Backend Son Hatalar:")
errs = run(f"docker logs {CONTAINER} --tail 50 2>&1 | grep -iE 'ERROR|Exception|Traceback|500|422' | tail -15")
print(errs if errs else "  Hata yok")

# ── 10. main.py eksik endpoint kontrolü ─────────────────────────────────
print("\n10. Backend Endpoint Varlik Kontrolu:")
ep_checks = [
    "evaluation/results",
    "api/warmup",
    "api/analyze-image",
    "api/gdpr",
    "api/admin",
    "channel_demo",
]
for ep in ep_checks:
    exists = run(f"grep -c '{ep}' /srv/anamnezai/backend/main.py 2>/dev/null || echo 0")
    try:
        cnt = int(exists.strip())
    except:
        cnt = 0
    print(f"  {'OK' if cnt > 0 else 'EKSIK'} [{cnt:2d}] {ep}")

client.close()
print("\n" + "=" * 70)
print("Denetim tamamlandi!")
print("=" * 70)


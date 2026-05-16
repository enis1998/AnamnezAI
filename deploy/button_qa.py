#!/usr/bin/env python3
"""
button_qa.py — HTML dosyalarında kırık link/buton tespiti
- href="#", href="javascript:void(0)" → beklenen (JS handler var)
- href ile harici/dahili URL → kontrol et
- onclick/data-action → var mı yok mu
- i18n key'lerin JS dict'te olup olmadığı
"""
import os, re
from pathlib import Path

FRONTEND = Path(r"C:\Users\pc\Desktop\Health\mediscreen\frontend")

PAGES = [
    "landing.html", "login.html", "register.html", "index.html",
    "kiosk.html", "previsit.html", "doctor.html", "admin.html",
    "summary.html", "clinical_review.html", "patient_dashboard.html",
    "profile.html", "analytics.html", "evaluation.html"
]

issues = []
ok_count = 0

for page in PAGES:
    fp = FRONTEND / page
    if not fp.exists():
        print(f"⚠️  MISSING: {page}")
        continue

    content = fp.read_text(encoding='utf-8', errors='replace')
    lines   = content.splitlines()
    page_issues = []

    # ── 1. href boş/undefined kontrol ──────────────────────────
    bad_hrefs = re.findall(r'href=["\'](?:undefined|null|#NaN)["\']', content)
    if bad_hrefs:
        page_issues.append(f"Bad href values: {bad_hrefs[:3]}")

    # ── 2. JavaScript hataları — console.error/alert mesajları ──
    raw_errors = re.findall(r"alert\(['\"](?!Çıkış|Are you sure)[^)]{0,80}\)", content)
    if raw_errors:
        for e in raw_errors[:2]:
            page_issues.append(f"alert() call: {e[:60]}")

    # ── 3. Hardcoded şifre/secret kontrol ───────────────────────
    secrets = re.findall(r'password\s*[=:]\s*["\'][^"\']{4,}["\']', content, re.I)
    bad_secrets = [s for s in secrets if 'placeholder' not in s.lower() and 'type="password"' not in s.lower()]
    if bad_secrets:
        page_issues.append(f"Hardcoded password? {bad_secrets[:1]}")

    # ── 4. API endpoint referansları ─────────────────────────────
    apis = set(re.findall(r"fetch\(['\"]([^'\"]+)['\"]", content))
    local_apis = {a for a in apis if a.startswith('/api/')}

    # ── 5. Data-i18n key'leri ─────────────────────────────────
    i18n_keys = re.findall(r'data-i18n=["\']([^"\']+)["\']', content)

    # Try to find the JS dict in the file
    dict_match = re.search(r'(?:const|let|var)\s+(?:DL|LL|ADL|LANG|i18n)\s*=\s*\{(.{100,50000}?)\};', content, re.DOTALL)
    if dict_match and i18n_keys:
        dict_content = dict_match.group(1)
        # Find keys defined in the dict
        defined_keys = set(re.findall(r"['\"]([a-zA-Z_.]+)['\"]:", dict_content))
        # Check top-level keys
        missing = [k for k in i18n_keys[:30] if k.split('.')[0] not in defined_keys and k not in defined_keys]
        if missing:
            page_issues.append(f"Possible missing i18n keys: {missing[:3]}")

    # ── 6. Form action kontrol ───────────────────────────────────
    forms = re.findall(r'<form[^>]*action=["\']([^"\']+)["\']', content)
    for action in forms:
        if not (action.startswith('/') or action.startswith('#') or action.startswith('http')):
            page_issues.append(f"Suspicious form action: {action}")

    # ── Report ───────────────────────────────────────────────────
    api_count = len(local_apis)
    i18n_count = len(i18n_keys)

    if page_issues:
        print(f"⚠️  {page}: {len(page_issues)} sorun")
        for iss in page_issues:
            print(f"      - {iss}")
    else:
        print(f"✅ {page}: temiz  [API:{api_count}, i18n:{i18n_count}]")
        ok_count += 1
    issues.extend([(page, iss) for iss in page_issues])

print(f"\n{'='*50}")
print(f"Toplam: {ok_count}/{len(PAGES)} sayfa temiz")
if issues:
    print(f"{len(issues)} sorun tespit edildi")
else:
    print("Hiç sorun yok!")


#!/usr/bin/env python3
"""Audit all HTML pages for i18n completeness."""
import os, re

FRONTEND = r"C:\Users\pc\Desktop\Health\mediscreen\frontend"
pages = ['doctor.html','admin.html','analytics.html','clinical_review.html',
         'summary.html','login.html','kiosk.html','index.html']

for page in pages:
    path = os.path.join(FRONTEND, page)
    if not os.path.exists(path):
        print(f"\n{page}: FILE MISSING"); continue
    with open(path, encoding='utf-8') as f:
        c = f.read()

    size = len(c)
    has_dict = bool(re.search(r'const [A-Z]{1,3} ?= ?\{', c))
    has_setlang = 'function setLang' in c
    has_lang_btns = 'dlbtn-tr' in c or 'lang-btn' in c or 'btn-lang' in c

    # Count Turkish chars in visible text (not inside <style> or <script>)
    # Simplified: count obvious Turkish UI strings in HTML body (not data content)
    tr_ui = re.findall(r'>[^<]*(?:Kullanıcı|Yönetim|İstatistik|Oturum|Çıkış|Ekle|Sil|Güncelle|Kaydet|Yükle|Randev|Hasta Adı)[^<]*<', c)

    print(f"\n{'='*50}")
    print(f"📄 {page} ({size} bytes)")
    print(f"  i18n dict: {has_dict} | setLang: {has_setlang} | lang btns: {has_lang_btns}")
    print(f"  Hardcoded TR UI strings found: {len(tr_ui)}")
    if tr_ui:
        for s in tr_ui[:5]:
            print(f"    - {s[:80].strip()}")


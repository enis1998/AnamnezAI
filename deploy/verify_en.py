#!/usr/bin/env python3
"""Sunucudaki HTML dosyalarında İngilizce varsayılan dil doğrulama"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)

def cmd(c):
    _, o, _ = ssh.exec_command(c)
    return o.read().decode().strip()

files = [
    'index.html','login.html','register.html','landing.html',
    'patient_dashboard.html','doctor.html','admin.html','summary.html',
    'kiosk.html','clinical_review.html','previsit.html'
]

print("\n" + "="*60)
print("  AnamnezAI EN Dil Doğrulama")
print("="*60)

all_ok = True
for f in files:
    path = f"/srv/anamnezai/frontend/{f}"
    has_lang_en  = cmd(f'grep -c "lang=\\"en\\"" {path} 2>/dev/null')
    has_lang_tr  = cmd(f'grep -c "lang=\\"tr\\"" {path} 2>/dev/null')
    has_def_tr   = cmd(f"grep -c \"|| 'tr'\" {path} 2>/dev/null")
    has_def_en   = cmd(f"grep -c \"|| 'en'\" {path} 2>/dev/null")
    title        = cmd(f'grep -o "<title>[^<]*</title>" {path} | head -1')

    ok = has_lang_tr == "0" and int(has_lang_en or "0") > 0 and has_def_tr == "0"
    status = "✅" if ok else "❌"
    if not ok:
        all_ok = False
    print(f"\n{status} {f}")
    print(f"   title   : {title}")
    print(f"   lang=en : {has_lang_en}  |  lang=tr: {has_lang_tr}  |  default_tr: {has_def_tr}  |  default_en: {has_def_en}")

ssh.close()
print("\n" + "="*60)
print("  SONUÇ:", "✅ TÜM DOSYALAR TAMAM" if all_ok else "❌ HATA BULUNDU")
print("="*60 + "\n")


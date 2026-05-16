#!/usr/bin/env python3
"""Check SSL certs and fix nginx if Let's Encrypt certs exist"""
import paramiko

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

# Check if Let's Encrypt certs exist
print("=== Let's Encrypt sertifikaları ===")
out = run("ls /etc/letsencrypt/live/ 2>/dev/null || echo 'Dizin yok'")
print(out)

out2 = run("ls /etc/letsencrypt/live/lifetrack.com.tr/ 2>/dev/null || echo 'lifetrack cert yok'")
print(out2)

# Check cert expiry if exists
out3 = run("openssl x509 -in /etc/letsencrypt/live/lifetrack.com.tr/cert.pem -noout -dates 2>/dev/null || echo 'Cert okuma hatası'")
print("Cert tarihler:", out3)

# See if Cloudflare Origin cert exists
out4 = run("ls /etc/ssl/cloudflare* 2>/dev/null || echo 'CF cert yok'")
print("CF certs:", out4)

# Check current nginx SSL
print("\n=== Mevcut nginx SSL satırları ===")
out5 = run("grep -n 'ssl_certificate' /etc/nginx/sites-enabled/lifetrack.com.tr")
print(out5)

# If cert exists, fix nginx config
cert_exists = "fullchain.pem" in run("ls /etc/letsencrypt/live/lifetrack.com.tr/ 2>/dev/null")
print(f"\nLetsEncrypt cert mevcut: {cert_exists}")

if cert_exists:
    print("\n🔧 nginx SSL → LetsEncrypt sertifikasına güncelleying...")
    run(r"sed -i 's|# ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;|ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;|g' /etc/nginx/sites-enabled/lifetrack.com.tr")
    run(r"sed -i 's|# ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;|ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;|g' /etc/nginx/sites-enabled/lifetrack.com.tr")
    run(r"sed -i 's|ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;|# ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;|g' /etc/nginx/sites-enabled/lifetrack.com.tr")
    run(r"sed -i 's|ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|# ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|g' /etc/nginx/sites-enabled/lifetrack.com.tr")

    out_t = run("nginx -t 2>&1")
    print("nginx -t:", out_t)
    if "successful" in out_t:
        run("systemctl reload nginx")
        print("✅ nginx reload edildi — LetsEncrypt sertifikası aktif!")
else:
    print("  → Snakeoil cert kullanılıyor. Cloudflare Flexible SSL modunda çalışıyor.")
    print("  → certbot ile LetsEncrypt almak için:")
    print("     certbot certonly --webroot -w /var/www/letsencrypt -d lifetrack.com.tr -d www.lifetrack.com.tr")

# Final connectivity test
print("\n=== Connectivity sonucu ===")
out6 = run("curl -sk --max-time 10 https://lifetrack.com.tr/healthz 2>/dev/null | head -100")
print("https://lifetrack.com.tr/healthz:", out6 or "(self-loop çalışmıyor — Cloudflare bypass)")
out7 = run("curl -sk --max-time 10 http://127.0.0.1:8001/healthz 2>/dev/null")
print("http://127.0.0.1:8001/healthz:", out7)

client.close()


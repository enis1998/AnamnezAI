#!/usr/bin/env python3
"""Run certbot to get Let's Encrypt cert for lifetrack.com.tr"""
import paramiko, time

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=120, show=True):
    if show:
        print(f"  $ {cmd[:90]}{'...' if len(cmd)>90 else ''}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    rc  = stdout.channel.recv_exit_status()
    combined = (out + '\n' + err).strip()
    if combined and show:
        print(f"    {combined[:500]}")
    return combined, rc

print("=== Step 1: certbot kurulumu ===")
out, _ = run("certbot --version 2>/dev/null || echo NOT_FOUND")
if "NOT_FOUND" in out or "not found" in out.lower():
    print("certbot yok, kuruluyor...")
    run("apt-get install -y certbot python3-certbot-nginx")
else:
    print(f"certbot mevcut: {out}")

print("\n=== Step 2: webroot dizini oluştur ===")
run("mkdir -p /var/www/letsencrypt/.well-known/acme-challenge")
run("echo 'test' > /var/www/letsencrypt/.well-known/acme-challenge/test.txt")

# Test if webroot is accessible via Cloudflare
print("\n=== Step 3: webroot erişilebilirlik testi ===")
out2, _ = run("curl -s --max-time 10 http://lifetrack.com.tr/.well-known/acme-challenge/test.txt 2>/dev/null || echo BLOCKED")
print(f"  webroot test: {out2[:100]}")

print("\n=== Step 4: Let's Encrypt cert al ===")
certbot_cmd = (
    "certbot certonly "
    "--webroot "
    "-w /var/www/letsencrypt "
    "-d lifetrack.com.tr "
    "-d www.lifetrack.com.tr "
    "--email admin@lifetrack.com.tr "
    "--agree-tos "
    "--non-interactive "
    "--force-renewal "
    "2>&1"
)
out3, rc = run(certbot_cmd, timeout=120)
print(f"  Exit code: {rc}")

if rc == 0 and "Congratulations" in out3:
    print("\n✅ LetsEncrypt cert alındı!")

    print("\n=== Step 5: nginx SSL → LetsEncrypt'e güncelle ===")
    NGINX_CONF = "/etc/nginx/sites-enabled/lifetrack.com.tr"
    # Uncomment LetsEncrypt lines
    run(r"sed -i 's|# ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;|ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;|g' " + NGINX_CONF)
    run(r"sed -i 's|# ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;|ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;|g' " + NGINX_CONF)
    # Comment out snakeoil
    run(r"sed -i 's|    ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;|    # ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;|g' " + NGINX_CONF)
    run(r"sed -i 's|    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|    # ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|g' " + NGINX_CONF)

    test_out, test_rc = run("nginx -t 2>&1")
    if test_rc == 0:
        run("systemctl reload nginx")
        print("✅ nginx LetsEncrypt sertifikası ile reload edildi!")
    else:
        print(f"❌ nginx -t hatası: {test_out}")
else:
    print(f"\n⚠️  certbot başarısız (rc={rc})")
    print("Çözüm önerileri:")
    print("  1. Cloudflare DNS proxy (orange cloud) OFF yapın, test edin, sonra tekrar açın")
    print("  2. Cloudflare → SSL/TLS → Overview'da 'Full' veya 'Full (Strict)' seçin")
    print("  3. Cloudflare Origin Certificate oluşturun:")
    print("     CF Dashboard → SSL/TLS → Origin Server → Create Certificate")
    print("     Sertifikayı /etc/ssl/cloudflare-origin.pem, key'i /etc/ssl/cloudflare-origin.key kaydedin")

client.close()


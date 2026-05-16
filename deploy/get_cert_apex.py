#!/usr/bin/env python3
"""Get Let's Encrypt cert for only lifetrack.com.tr (no www)"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=120):
    print(f"  $ {cmd[:90]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    rc  = stdout.channel.recv_exit_status()
    combined = (out + '\n' + err).strip()
    if combined:
        print(f"    {combined[:600]}")
    return combined, rc

# Only apex domain (www. has no DNS record)
print("=== certbot: sadece lifetrack.com.tr (www. hariç) ===")
out, rc = run(
    "certbot certonly "
    "--webroot "
    "-w /var/www/letsencrypt "
    "-d lifetrack.com.tr "
    "--email admin@lifetrack.com.tr "
    "--agree-tos "
    "--non-interactive "
    "--force-renewal "
    "2>&1",
    timeout=120
)
print(f"\nExit code: {rc}")

if rc == 0 and "Congratulations" in out:
    print("\n✅ LetsEncrypt cert alındı!")
    NGINX_CONF = "/etc/nginx/sites-enabled/lifetrack.com.tr"

    # Also update sites-available
    NGINX_AVAIL = "/etc/nginx/sites-available/lifetrack.com.tr"
    for conf in [NGINX_CONF, NGINX_AVAIL]:
        run(r"sed -i 's|# ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;|ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;|g' " + conf)
        run(r"sed -i 's|# ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;|ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;|g' " + conf)
        run(r"sed -i 's|    ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;|    # ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;|g' " + conf)
        run(r"sed -i 's|    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|    # ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|g' " + conf)

    # Remove www from server_name too
    for conf in [NGINX_CONF, NGINX_AVAIL]:
        run(f"sed -i 's/server_name lifetrack.com.tr www.lifetrack.com.tr;/server_name lifetrack.com.tr;/g' {conf}")

    test_out, test_rc = run("nginx -t 2>&1")
    if test_rc == 0:
        run("systemctl reload nginx")
        print("\n✅ nginx reload edildi — gerçek SSL aktif!")
    else:
        print(f"❌ nginx -t hatası: {test_out}")

    # Verify cert
    run("certbot certificates 2>&1 | grep -A5 lifetrack")
else:
    print(f"\n⚠️  certbot başarısız. Webroot HTTP erişim sorunu olabilir.")
    print("Webroot test:")
    run("curl -svI --max-time 5 http://lifetrack.com.tr/.well-known/acme-challenge/test.txt 2>&1 | head -20")

client.close()


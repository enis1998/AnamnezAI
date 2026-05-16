#!/usr/bin/env python3
"""Update nginx to use the newly obtained LetsEncrypt cert"""
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=USER, password=PASS,
               timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, timeout=30):
    print(f"  $ {cmd[:90]}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    rc  = stdout.channel.recv_exit_status()
    combined = (out + '\n' + err).strip()
    if combined:
        print(f"    {combined[:400]}")
    return combined, rc

# Verify cert exists
run("ls -la /etc/letsencrypt/live/lifetrack.com.tr/")

# Write a new clean nginx config with LetsEncrypt cert
new_conf = r"""# /etc/nginx/sites-available/lifetrack.com.tr — AnamnezAI
# LetsEncrypt cert aktif (certbot 2026-05-15)

server {
    listen 80;
    listen [::]:80;
    server_name lifetrack.com.tr;

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
        default_type text/plain;
    }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name lifetrack.com.tr;

    ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL_LT:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 50M;

    # Font ve CSS dosyalari icin cache
    location ~* \.(woff2|woff|ttf)$ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "public, max-age=86400";
    }

    # SSE (Server-Sent Events) icin buffer devre disi
    location /api/session/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_connect_timeout 30s;
        chunked_transfer_encoding on;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 30s;
    }
}
"""

print("\n=== nginx config güncelleniyor (LetsEncrypt) ===")
# Write new config
import io
sftp = client.open_sftp()
with sftp.open("/etc/nginx/sites-available/lifetrack.com.tr", 'w') as f:
    f.write(new_conf)
sftp.close()
print("  ✅ sites-available/lifetrack.com.tr güncellendi")

# Update symlink (recreate to ensure it points to new file)
run("ln -sf /etc/nginx/sites-available/lifetrack.com.tr /etc/nginx/sites-enabled/lifetrack.com.tr")
print("  ✅ symlink güncellendi")

# Test and reload
test_out, test_rc = run("nginx -t 2>&1")
if test_rc == 0:
    run("systemctl reload nginx")
    print("\n✅ nginx LetsEncrypt sertifikasıyla reload edildi!")
else:
    print(f"❌ nginx -t hatası!")

# Final check
print("\n=== SSL doğrulama ===")
run("openssl x509 -in /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem -noout -subject -dates 2>&1")
run("curl -sI --max-time 5 http://127.0.0.1:8001/healthz | head -2")

client.close()
print("\n✅ Tamamlandı!")


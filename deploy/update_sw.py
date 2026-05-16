import paramiko

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

sftp = client.open_sftp()

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode().strip()
    print(f"  $ {cmd[:80]}")
    if out: print(f"  {out[:200]}")
    return out

print("📤 sw.js güncelleniyor (v5 → v6)...")
sftp.put(r"C:\Users\pc\Desktop\Health\mediscreen\frontend\sw.js",
         "/srv/anamnezai/frontend/sw.js")
run("docker cp /srv/anamnezai/frontend/sw.js anamnezai-backend-1:/app/frontend/sw.js")
run("docker exec anamnezai-backend-1 grep CACHE_NAME /app/frontend/sw.js")
print("  ✅ sw.js güncellendi")

# Nginx'in etag/cache-control ayarlarını kontrol et
print("\n🔧 Nginx static file cache kontrolü...")
run("grep -n 'expires\\|cache\\|etag' /etc/nginx/sites-enabled/lifetrack.com.tr")

# Nginx'e no-cache header ekle (font/css dosyaları için)
nginx_font_cache = """
    # Font ve CSS dosyaları için cache-control
    location ~* \\.(woff2|woff|ttf|css)$ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "public, max-age=86400";
        proxy_buffering on;
    }
"""

# Mevcut config'e SSE location'dan önce ekle
run(r"""sed -i '/# SSE (Server-Sent Events)/i\    # Font ve CSS dosyalari icin cache\n    location ~* \\.(woff2|woff|ttf)$ {\n        proxy_pass http:\/\/127.0.0.1:8001;\n        proxy_set_header Host $host;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        add_header Cache-Control "public, max-age=86400";\n    }\n' /etc/nginx/sites-enabled/lifetrack.com.tr""")

run("nginx -t 2>&1 && systemctl reload nginx || echo 'nginx config error'")

sftp.close()
client.close()
print("\n✅ Tamamlandı! Tarayıcıda Ctrl+Shift+R ile hard refresh yapın.")


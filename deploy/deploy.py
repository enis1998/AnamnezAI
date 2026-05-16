#!/usr/bin/env python3
"""
AnamnezAI Sunucu Deployment Scripti
- Root ile bağlanır
- /srv/anamnezai dizini oluşturur
- Dosyaları SFTP ile yükler
- Ollama kurar
- docker-compose başlatır
- nginx yapılandırır
"""
import paramiko
import os
import sys
import time
import stat

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"
POSTGRES_PASSWORD = "XD5eu2RhyHjvSP4MHCanU7Ya"

PROJECT_LOCAL = r"C:\Users\pc\Desktop\Health\mediscreen"
PROJECT_REMOTE = "/srv/anamnezai"
BACKEND_PORT = 8001  # 8000 zaten dolu

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Root bağlantısı başarılı")

def run(cmd, timeout=60, ignore_error=False):
    print(f"  $ {cmd[:80]}{'...' if len(cmd)>80 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0 and not ignore_error:
        print(f"  [stderr] {err.strip()[:200]}")
    else:
        if out.strip():
            print(f"  {out.strip()[:200]}")
    return out.strip(), err.strip(), exit_code

def run_bg(cmd):
    """Arka planda çalıştır, çıktı bekleme"""
    print(f"  [bg] $ {cmd[:80]}")
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdin, stdout, stderr


# ─── ADIM 1: Dizin yapısını oluştur ──────────────────────────────────────────
print("\n📁 ADIM 1: Dizin yapısı oluşturuluyor...")
run(f"mkdir -p {PROJECT_REMOTE}")
run(f"mkdir -p {PROJECT_REMOTE}/backend")
run(f"mkdir -p {PROJECT_REMOTE}/frontend")
run(f"mkdir -p {PROJECT_REMOTE}/chroma_db")
print("  Dizinler oluşturuldu.")

# ─── ADIM 2: Dosyaları SFTP ile yükle ────────────────────────────────────────
print("\n📤 ADIM 2: Dosyalar yükleniyor...")

sftp = client.open_sftp()

def upload_file(local_path, remote_path):
    try:
        sftp.put(local_path, remote_path)
        print(f"  ✅ {os.path.basename(local_path)}")
        return True
    except Exception as e:
        print(f"  ❌ {os.path.basename(local_path)}: {e}")
        return False

def upload_dir(local_dir, remote_dir, extensions=None, skip_dirs=None):
    skip_dirs = skip_dirs or ['__pycache__', '.git', 'node_modules']
    for root_dir, dirs, files in os.walk(local_dir):
        # Skip istenen dizinler
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel = os.path.relpath(root_dir, local_dir)
        if rel == '.':
            remote_sub = remote_dir
        else:
            remote_sub = remote_dir + '/' + rel.replace('\\', '/')
        try:
            sftp.mkdir(remote_sub)
        except:
            pass
        for f in files:
            if extensions and not any(f.endswith(e) for e in extensions):
                continue
            local_f = os.path.join(root_dir, f)
            remote_f = remote_sub + '/' + f
            upload_file(local_f, remote_f)

# Backend Python dosyaları
print("\n  [Backend]")
upload_dir(
    os.path.join(PROJECT_LOCAL, "backend"),
    f"{PROJECT_REMOTE}/backend",
    extensions=['.py', '.txt', '.json', '.yaml', '.yml', '.md'],
    skip_dirs=['__pycache__', 'tests']
)

# Frontend HTML/JS/CSS/JSON dosyaları
print("\n  [Frontend]")
upload_dir(
    os.path.join(PROJECT_LOCAL, "frontend"),
    f"{PROJECT_REMOTE}/frontend",
    extensions=['.html', '.js', '.css', '.json', '.png', '.svg', '.ico', '.webp', '.jpg'],
    skip_dirs=['__pycache__']
)

# Kök dizin dosyaları
print("\n  [Root dosyalar]")
for fname in ['Dockerfile', 'docker-compose.yml', 'README.md', 'GEMMA4_MODEL_CARD.md']:
    local_f = os.path.join(PROJECT_LOCAL, fname)
    if os.path.exists(local_f):
        upload_file(local_f, f"{PROJECT_REMOTE}/{fname}")

sftp.close()

# ─── ADIM 3: .env dosyası oluştur ────────────────────────────────────────────
print("\n⚙️  ADIM 3: .env dosyası oluşturuluyor...")
env_content = f"""# AnamnezAI Production .env
POSTGRES_PASSWORD={POSTGRES_PASSWORD}
GEMMA_MODEL=gemma4:e4b
MEDGEMMA_MODEL=medgemma:4b
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_NUM_GPU=99
RAG_ENABLED=true
JWT_SECRET_KEY=anamnezai_prod_jwt_secret_2026_lifetrack
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=anamnezai
POSTGRES_USER=anamnezai
"""
cmd = f"cat > {PROJECT_REMOTE}/.env << 'ENVEOF'\n{env_content}\nENVEOF"
run(cmd)
print("  .env oluşturuldu.")

# ─── ADIM 4: docker-compose.yml port 8001 olarak güncelle ────────────────────
print("\n🐳 ADIM 4: docker-compose.yml port 8001'e güncelleniyor...")
run(f"sed -i 's/\"8000:8000\"/\"8001:8000\"/' {PROJECT_REMOTE}/docker-compose.yml")
out, _, _ = run(f"grep 'ports' -A2 {PROJECT_REMOTE}/docker-compose.yml")
print(f"  Port: {out}")

# ─── ADIM 5: Ollama kur ───────────────────────────────────────────────────────
print("\n🦙 ADIM 5: Ollama kuruluyor...")
out, _, rc = run("which ollama 2>/dev/null || echo NOT_FOUND", ignore_error=True)
if "NOT_FOUND" in out or not out:
    print("  Ollama yüklü değil, kuruluyor...")
    run("curl -fsSL https://ollama.com/install.sh | sh", timeout=300)
    # Ollama servis başlat
    run("systemctl enable ollama", ignore_error=True)
    run("systemctl start ollama", ignore_error=True)
    time.sleep(5)
    out, _, _ = run("ollama --version", ignore_error=True)
    print(f"  Ollama: {out}")
else:
    print(f"  Ollama zaten kurulu: {out}")

# Ollama çalışıyor mu?
out, _, _ = run("systemctl is-active ollama 2>/dev/null || echo inactive", ignore_error=True)
print(f"  Ollama servis durumu: {out}")

# ─── ADIM 6: Docker grubuna enis ekle ────────────────────────────────────────
print("\n👤 ADIM 6: enis kullanıcısı docker grubuna ekleniyor...")
run("usermod -aG docker enis", ignore_error=True)
out, _, _ = run("getent group docker")
print(f"  docker grubu: {out}")

# ─── ADIM 7: Docker compose başlat ───────────────────────────────────────────
print("\n🚀 ADIM 7: Docker compose başlatılıyor...")
run(f"cd {PROJECT_REMOTE} && docker compose down 2>/dev/null || true", ignore_error=True)
run(f"cd {PROJECT_REMOTE} && docker compose build --no-cache", timeout=600)
run(f"cd {PROJECT_REMOTE} && docker compose up -d", timeout=120)
time.sleep(10)
out, _, _ = run("docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'")
print(f"\n  Çalışan containers:\n{out}")

# ─── ADIM 8: Backend sağlık kontrolü ─────────────────────────────────────────
print("\n🏥 ADIM 8: Backend yanıt kontrolü...")
time.sleep(8)
out, _, _ = run("curl -s --max-time 5 http://localhost:8001/healthz", ignore_error=True)
print(f"  /healthz yanıtı: {out}")

# ─── ADIM 9: Nginx yapılandır ─────────────────────────────────────────────────
print("\n🌐 ADIM 9: Nginx yapılandırılıyor (lifetrack.com.tr)...")

nginx_conf = """# /etc/nginx/sites-available/lifetrack.com.tr — AnamnezAI
# Backend container: anamnezai-backend-1 at 127.0.0.1:8001

server {
    listen 80;
    listen [::]:80;
    server_name lifetrack.com.tr www.lifetrack.com.tr;

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
        default_type text/plain;
    }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name lifetrack.com.tr www.lifetrack.com.tr;

    # SSL — certbot sonrası bu blok aktif olacak
    # ssl_certificate     /etc/letsencrypt/live/lifetrack.com.tr/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/lifetrack.com.tr/privkey.pem;

    # Geçici self-signed (certbot öncesi)
    ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL_LT:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 50M;

    # SSE (Server-Sent Events) için buffer devre dışı
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

# Nginx config dosyasına yaz
run(f"cat > /etc/nginx/sites-available/lifetrack.com.tr << 'NGINXEOF'\n{nginx_conf}\nNGINXEOF")
run("ln -sf /etc/nginx/sites-available/lifetrack.com.tr /etc/nginx/sites-enabled/lifetrack.com.tr",
    ignore_error=True)

# Nginx test
out, err, rc = run("nginx -t 2>&1", ignore_error=True)
print(f"  nginx -t: {out} {err}")

if rc == 0:
    run("systemctl reload nginx")
    print("  Nginx yeniden yüklendi.")
else:
    print("  ⚠️ Nginx config hatası! Manuel kontrol gerekli.")

# ─── ADIM 10: Özet ────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("✅ DEPLOYMENT TAMAMLANDI")
print("="*60)
print(f"""
📍 Sunucu:        {HOST}
🗂️  Proje dizini:  {PROJECT_REMOTE}
🐳 Backend port:  8001 (docker container)
🌐 Domain:        lifetrack.com.tr

⚠️  YAPILMASI GEREKENLER:
1. DNS GÜNCELLEMESI (SİZ YAPACAKSINIZ):
   lifetrack.com.tr → 195.87.198.163 (A kaydı)
   www.lifetrack.com.tr → 195.87.198.163 (A kaydı)

2. DNS yayıldıktan sonra SSL sertifikası:
   certbot --nginx -d lifetrack.com.tr -d www.lifetrack.com.tr

3. Ollama modeli (yavaş olacak, arka planda):
   ollama pull gemma4:e4b

🔗 HTTP test (VPN ile): http://10.200.9.11:8001/
""")

client.close()


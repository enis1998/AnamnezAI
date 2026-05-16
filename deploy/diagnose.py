import paramiko

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

def run(cmd, timeout=30, ignore_error=False):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return (out + err).strip()

# Nginx access/error logları
print("=== NGINX ERROR LOG (son 30) ===")
print(run("tail -30 /var/log/nginx/error.log"))

print("\n=== NGINX ACCESS LOG (son 20 - lifetrack) ===")
print(run("tail -50 /var/log/nginx/access.log | grep -i lifetrack | tail -20"))

# Backend vendor dizini var mı?
print("\n=== Backend vendor/ dizini ===")
print(run("ls /srv/anamnezai/frontend/vendor/ 2>/dev/null || echo 'VENDOR DİZİNİ YOK!'"))

# Frontend'de statik dosya kontrolü
print("\n=== Frontend statik dosyalar ===")
print(run("find /srv/anamnezai/frontend -name '*.css' -o -name '*.js' | head -20"))

# Backend 404 testleri (vendor dosyaları)
print("\n=== Vendor dosyaları HTTP testi ===")
test_paths = [
    "/vendor/tailwind.min.js",
    "/vendor/chart.umd.min.js",
    "/vendor/jspdf.umd.min.js",
    "/vendor/html2canvas.min.js",
    "/vendor/googlefonts_manrope_inter.css",
    "/vendor/local_fonts.css",
    "/vendor/material_symbols.css",
]
for path in test_paths:
    code = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8001{path}")
    status = "✅" if code == "200" else "❌"
    print(f"  {status} {code} {path}")

# index.html içinde vendor referansları
print("\n=== index.html vendor referansları ===")
print(run("grep -n 'vendor\\|tailwind\\|chart\\|jspdf\\|fonts' /srv/anamnezai/frontend/index.html | head -20"))

# screens/ dizini
print("\n=== screens/ dizini ===")
print(run("ls /srv/anamnezai/frontend/screens/ 2>/dev/null || echo 'screens/ YOK'"))

# Nginx lifetrack config
print("\n=== Nginx lifetrack config ===")
print(run("cat /etc/nginx/sites-enabled/lifetrack.com.tr 2>/dev/null | head -20 || echo 'config yok'"))

# DNS durumu
print("\n=== lifetrack.com.tr DNS ===")
print(run("dig +short lifetrack.com.tr 2>/dev/null || host lifetrack.com.tr 2>/dev/null | head -3"))

client.close()


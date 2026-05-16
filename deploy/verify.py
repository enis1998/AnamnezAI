import paramiko

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode().strip()

# Kritik font dosyaları HTTP testi
print("=== Font & CSS 404 kontrolü ===")
tests = [
    "/vendor/fonts/material_symbols_outlined.woff2",
    "/vendor/fonts/font_5.woff2",
    "/vendor/fonts/font_6.woff2",
    "/vendor/fonts/font_32.woff2",
    "/vendor/fonts/font_33.woff2",
    "/vendor/fonts/local_fonts.css",
    "/vendor/fonts/material_symbols_local.css",
    "/vendor/fonts/googlefonts_manrope_inter.css",
    "/vendor/tailwind.min.js",
    "/vendor/chart.umd.min.js",
]
for path in tests:
    code = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8001{path}")
    icon = "✅" if code == "200" else "❌"
    print(f"  {icon} HTTP {code}  {path}")

# Son access log satırları
print("\n=== Son nginx access log (404'ler) ===")
print(run("tail -20 /var/log/nginx/access.log | grep ' 404 '"))

# Ollama model durumu
print("\n=== Ollama model durumu ===")
print(run("ollama list"))

# Backend health
print("\n=== Backend health ===")
print(run("curl -s http://localhost:8001/health | python3 -c \"import sys,json; d=json.load(sys.stdin); print('ollama:', d['ollama'], '| model:', d.get('gemma_available','?'))\""))

client.close()
print("\n✅ Kontrol tamamlandı.")


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

# CSS içeriklerini kontrol et
print("=== material_symbols_local.css ===")
print(run("docker exec anamnezai-backend-1 cat /app/frontend/vendor/fonts/material_symbols_local.css"))

print("\n=== material_symbols.css ===")
print(run("docker exec anamnezai-backend-1 cat /app/frontend/vendor/fonts/material_symbols.css"))

print("\n=== local_fonts.css (ilk 30 satır) ===")
print(run("docker exec anamnezai-backend-1 head -30 /app/frontend/vendor/fonts/local_fonts.css"))

# index.html CSS/font referansları
print("\n=== index.html <head> CSS referansları ===")
print(run("docker exec anamnezai-backend-1 head -30 /app/frontend/index.html"))

# landing.html CSS referansları
print("\n=== landing.html <head> CSS referansları ===")
print(run("docker exec anamnezai-backend-1 head -25 /app/frontend/landing.html"))

# HTTP ile font dosyası doğrula
print("\n=== HTTP font dosyası kontrolü ===")
paths = [
    "/vendor/fonts/material_symbols_outlined.woff2",
    "/vendor/fonts/material_symbols_local.css",
    "/vendor/fonts/material_symbols.css",
    "/vendor/fonts/local_fonts.css",
]
for p in paths:
    code = run(f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8001{p}")
    print(f"  {'✅' if code=='200' else '❌'} {code} {p}")

client.close()


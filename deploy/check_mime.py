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

# woff2 Content-Type kontrolü
print("=== woff2 Content-Type ===")
print(run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_outlined.woff2 | grep -E 'Content-Type|HTTP'"))

# CSS Content-Type
print("\n=== CSS Content-Type ===")
print(run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_local.css | grep -E 'Content-Type|HTTP'"))

# FastAPI StaticFiles kaydı kontrol
print("\n=== main.py StaticFiles mount ===")
print(run("docker exec anamnezai-backend-1 grep -n 'StaticFiles\\|mount\\|static\\|frontend' /app/main.py | head -15"))

# Python aiofiles / starlette woff2 mime type
print("\n=== Python default MIME types ===")
print(run("docker exec anamnezai-backend-1 python3 -c \"import mimetypes; print(mimetypes.guess_type('test.woff2')); print(mimetypes.guess_type('test.css'))\""))

# Eğer mime type None ise, add_type eklenmiş mi?
print("\n=== main.py mime type kayıtları ===")
print(run("docker exec anamnezai-backend-1 grep -n 'mime\\|woff\\|add_type\\|types' /app/main.py | head -10"))

client.close()


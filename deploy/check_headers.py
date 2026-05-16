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

# Tam header
print("=== woff2 tam header ===")
print(run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_outlined.woff2"))

print("\n=== CSS tam header ===")
print(run("curl -sI http://localhost:8001/vendor/fonts/material_symbols_local.css"))

# main.py'deki mimetypes satırları
print("\n=== main.py mimetypes kontrol ===")
print(run("docker exec anamnezai-backend-1 grep -n 'mimetypes' /app/main.py | head -10"))

# Python runtime'da kontrol
print("\n=== Runtime MIME type ===")
print(run("docker exec anamnezai-backend-1 python3 -c \"import mimetypes; print(mimetypes.guess_type('test.woff2')); print(mimetypes.guess_type('test.css'))\""))

client.close()


import paramiko

HOST = "10.200.9.11"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username="root", password="nWTGzzDqwyFyNJhqMhvcjEJj",
               timeout=15, look_for_keys=False, allow_agent=False)
sftp = client.open_sftp()

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (stdout.read() + stderr.read()).decode().strip()

# 1) doctor.html
print("Uploading doctor.html...")
sftp.put(r"C:\Users\pc\Desktop\Health\mediscreen\frontend\doctor.html",
         "/srv/anamnezai/frontend/doctor.html")
print("  doctor.html OK")

# 2) sw.js
print("Uploading sw.js...")
sftp.put(r"C:\Users\pc\Desktop\Health\mediscreen\frontend\sw.js",
         "/srv/anamnezai/frontend/sw.js")
print("  sw.js OK")

# Dogrulama
print("\nDogrulama:")
dl = run("grep -c 'const DL' /srv/anamnezai/frontend/doctor.html")
print(f"  const DL count: {dl} (1 olmali)")

tfn = run("grep -c 'function t(key' /srv/anamnezai/frontend/doctor.html")
print(f"  function t(key) count: {tfn} (1 olmali)")

# DL'nin hangi satirda oldugunu goster
dl_line = run("grep -n 'const DL' /srv/anamnezai/frontend/doctor.html")
print(f"  const DL satiri: {dl_line}")

# loadQueue'nun hangi satirda oldugunu goster
lq_lines = run("grep -n 'loadQueue()' /srv/anamnezai/frontend/doctor.html | grep -v onclick | grep -v 'loadQueue(' | head -5")
print(f"  loadQueue() cagrilari: {lq_lines}")

sw_ver = run("grep -o 'anamnezai-v[0-9]*' /srv/anamnezai/frontend/sw.js")
print(f"  SW version: {sw_ver} (v8 olmali)")

sftp.close()
client.close()
print("\nTamam! Kullanici tarayicisini yenilemeli.")


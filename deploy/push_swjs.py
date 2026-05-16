import paramiko

HOST = "10.200.9.11"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username="root", password="nWTGzzDqwyFyNJhqMhvcjEJj",
               timeout=15, look_for_keys=False, allow_agent=False)
sftp = client.open_sftp()

sftp.put(r"C:\Users\pc\Desktop\Health\mediscreen\frontend\sw.js",
         "/srv/anamnezai/frontend/sw.js")
print("sw.js guncellendi")

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    return (stdout.read() + stderr.read()).decode().strip()

ver = run("grep -o 'anamnezai-v[0-9]*' /srv/anamnezai/frontend/sw.js")
print("Cache version:", ver)

dl = run("grep -c 'const DL' /srv/anamnezai/frontend/doctor.html")
print("doctor.html const DL count:", dl)

sftp.close()
client.close()
print("Tamam!")


import paramiko

HOST = '10.200.9.11'
ROOT_USER = 'root'
ROOT_PASS = 'nWTGzzDqwyFyNJhqMhvcjEJj'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

def run(cmd):
    _, so, se = client.exec_command(cmd, timeout=20)
    return (so.read() + se.read()).decode().strip()

print("=== admin.html EN translations check ===")
r = run("grep -c 'txt-stat-total-users' /srv/anamnezai/frontend/admin.html")
print(f"  txt-stat-total-users count: {r}")
r = run("grep -c 'setAdminLang' /srv/anamnezai/frontend/admin.html")
print(f"  setAdminLang count: {r}")
r = run("grep -c 'Total Users' /srv/anamnezai/frontend/admin.html")
print(f"  EN 'Total Users': {r}")
r = run("grep -c 'txt-btn-csv' /srv/anamnezai/frontend/admin.html")
print(f"  txt-btn-csv: {r}")
r = run("grep -c 'statTotalUsers' /srv/anamnezai/frontend/admin.html")
print(f"  statTotalUsers in ADL: {r}")

print("\n=== doctor.html EN previsit check ===")
r = run("grep -c 'previsitTitle' /srv/anamnezai/frontend/doctor.html")
print(f"  previsitTitle in DL: {r}")
r = run("grep -c 'Appointments' /srv/anamnezai/frontend/doctor.html")
print(f"  'Appointments' count: {r}")

print("\n=== clinical_review.html CR_DICT check ===")
r = run("grep -c 'CR_DICT' /srv/anamnezai/frontend/clinical_review.html")
print(f"  CR_DICT count: {r}")
r = run("grep -c 'applyCRLang' /srv/anamnezai/frontend/clinical_review.html")
print(f"  applyCRLang count: {r}")

print("\n=== summary.html SM_DICT check ===")
r = run("grep -c 'SM_DICT' /srv/anamnezai/frontend/summary.html")
print(f"  SM_DICT count: {r}")

print("\n=== Container sync check ===")
r = run("docker exec anamnezai-backend-1 grep -c 'setAdminLang' /app/frontend/admin.html 2>&1 || echo 'not synced'")
print(f"  Container admin.html setAdminLang: {r}")
r = run("docker exec anamnezai-backend-1 grep -c 'Total Users' /app/frontend/admin.html 2>&1 || echo '0'")
print(f"  Container admin.html EN Total Users: {r}")

client.close()
print("\nAll checks done!")


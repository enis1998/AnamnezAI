import paramiko

HOST = '10.200.9.11'
ROOT_USER = 'root'
ROOT_PASS = 'nWTGzzDqwyFyNJhqMhvcjEJj'
CONTAINER = 'anamnezai-backend-1'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)

def run(cmd):
    _, so, se = client.exec_command(cmd, timeout=30)
    out = (so.read() + se.read()).decode().strip()
    print(f"  $ {cmd[:80]}")
    if out: print(f"  > {out[:200]}")
    return out

FILES = [
    'doctor.html', 'admin.html', 'clinical_review.html',
    'summary.html', 'login.html', 'index.html', 'kiosk.html'
]

SFTP_BASE = '/srv/anamnezai/frontend'
CONTAINER_BASE = '/app/frontend'

print("=== Syncing files to Docker container ===")
for f in FILES:
    src = f"{SFTP_BASE}/{f}"
    dst = f"{CONTAINER_BASE}/{f}"
    r = run(f"docker cp {src} {CONTAINER}:{dst} && echo OK || echo FAIL")

print("\n=== Verification ===")
checks = {
    'admin.html': ['txt-stat-total-users', 'Total Users', 'statTotalUsers'],
    'doctor.html': ['previsitTitle', 'txt-previsit-title'],
    'clinical_review.html': ['CR_DICT', 'applyCRLang'],
    'summary.html': ['SM_DICT'],
}

for fname, patterns in checks.items():
    print(f"\n{fname}:")
    for pattern in patterns:
        r = run(f"docker exec {CONTAINER} grep -c '{pattern}' {CONTAINER_BASE}/{fname} 2>&1")
        status = 'OK' if r.strip() != '0' and r.strip() != '' else 'MISSING'
        print(f"  {pattern}: {r.strip()} [{status}]")

client.close()
print("\nSync complete!")


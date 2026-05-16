#!/usr/bin/env python3
"""Deploy i18n fix - lang button active state + patient dashboard full i18n"""
import subprocess, sys, os

HOST    = "10.200.9.11"
USER    = "root"
PASS    = "nWTGzzDqwyFyNJhqMhvcjEJj"
REMOTE  = "/srv/anamnezai/frontend"
CONTAINER = "anamnezai-backend-1"
CDIR    = "/app/frontend"

BASE = os.path.join(os.path.dirname(__file__), "..", "frontend")

FILES = [
    "patient_dashboard.html",  # full i18n (first deploy)
    "index.html",              # TR btn bg-pric removed
    "doctor.html",             # TR btn bg-pric removed
    "admin.html",              # TR btn bg-white removed
]

def run(cmd):
    print(f"  ▶ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.stdout.strip(): print("   ", r.stdout.strip()[:300])
    if r.stderr.strip(): print("  !", r.stderr.strip()[:300])
    return r.returncode

def scp(local, remote):
    cmd = f'sshpass -p "{PASS}" scp -o StrictHostKeyChecking=no "{local}" {USER}@{HOST}:{remote}'
    return run(cmd)

def ssh(cmd_remote):
    cmd = f'sshpass -p "{PASS}" ssh -o StrictHostKeyChecking=no {USER}@{HOST} "{cmd_remote}"'
    return run(cmd)

print("=== Deploying i18n fix (lang buttons + patient dashboard) ===\n")

ok = 0
for fname in FILES:
    local = os.path.normpath(os.path.join(BASE, fname))
    print(f"\n[{fname}]")
    if not os.path.exists(local):
        print(f"  ✗ Not found: {local}")
        continue
    # SCP to server
    rc = scp(local, f"{REMOTE}/{fname}")
    if rc != 0:
        print(f"  ✗ SCP failed for {fname}")
        continue
    # docker cp into container
    rc = ssh(f"docker cp {REMOTE}/{fname} {CONTAINER}:{CDIR}/{fname}")
    if rc != 0:
        print(f"  ✗ docker cp failed for {fname}")
        continue
    print(f"  ✓ {fname} deployed")
    ok += 1

print(f"\n=== Done: {ok}/{len(FILES)} files deployed ===")

# Nginx reload
print("\nReloading nginx in container...")
ssh(f"docker exec {CONTAINER} nginx -s reload 2>/dev/null || true")
print("Done.")


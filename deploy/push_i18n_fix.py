#!/usr/bin/env python3
"""Push i18n-fixed files to live server."""
import subprocess, sys, os

SSH_HOST = "lifetrack.com.tr"
SSH_USER = "root"
CONTAINER = "anamnezai-backend-1"
FRONTEND = r"C:\Users\pc\Desktop\Health\mediscreen\frontend"
BACKEND = r"C:\Users\pc\Desktop\Health\mediscreen\backend"

def ssh(cmd, show=True):
    if show: print(f"  SSH: {cmd[:80]}")
    r = subprocess.run(
        ["ssh", f"{SSH_USER}@{SSH_HOST}", cmd],
        capture_output=True, text=True
    )
    if r.returncode != 0 and r.stderr:
        print(f"  WARN: {r.stderr[:100]}")
    return r.stdout.strip()

def scp(local, remote):
    print(f"  SCP: {os.path.basename(local)} -> {remote}")
    r = subprocess.run(
        ["scp", local, f"{SSH_USER}@{SSH_HOST}:{remote}"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr[:100]}")
        return False
    return True

def docker_cp(local, container_path):
    fname = os.path.basename(local)
    print(f"  docker cp: {fname} -> {container_path}")
    r = subprocess.run(
        ["ssh", f"{SSH_USER}@{SSH_HOST}",
         f"docker cp /tmp/{fname} {CONTAINER}:{container_path}"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr[:100]}")
        return False
    return True

print("=" * 60)
print("PUSH: i18n-fixed frontend files to lifetrack.com.tr")
print("=" * 60)

# Files to push
FRONTEND_FILES = [
    "doctor.html",
    "admin.html",
    "clinical_review.html",
    "summary.html",
    "index.html",
    "kiosk.html",
    "login.html",
]

# 1. Copy to /tmp on server
print("\n[1] Uploading to /tmp on server...")
for fname in FRONTEND_FILES:
    local = os.path.join(FRONTEND, fname)
    if os.path.exists(local):
        scp(local, f"/tmp/{fname}")
    else:
        print(f"  SKIP (not found): {fname}")

# 2. Move to nginx root
print("\n[2] Moving to nginx root /var/www/html/...")
for fname in FRONTEND_FILES:
    local = os.path.join(FRONTEND, fname)
    if os.path.exists(local):
        ssh(f"cp /tmp/{fname} /var/www/html/{fname}")
        print(f"  ✓ /var/www/html/{fname}")

# 3. Copy to Docker container
print("\n[3] Copying to Docker container...")
for fname in FRONTEND_FILES:
    local = os.path.join(FRONTEND, fname)
    if os.path.exists(local):
        docker_cp(local, f"/app/frontend/{fname}")

# 4. Verify container is healthy
print("\n[4] Checking container health...")
status = ssh(f"docker inspect --format='{{{{.State.Status}}}}' {CONTAINER}")
print(f"  Container status: {status}")
health = ssh(f"docker inspect --format='{{{{.State.Health.Status}}}}' {CONTAINER}")
print(f"  Health: {health}")

import urllib.request
print("\n[5] Testing endpoints...")
for path in ["/healthz", "/api/public/landing-metrics"]:
    try:
        url = f"https://{SSH_HOST}{path}"
        req = urllib.request.Request(url)
        import ssl; ctx = ssl.create_default_context()
        ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=5) as r:
            body = r.read(200).decode()
            print(f"  {path}: HTTP {r.status} {body[:60]}")
    except Exception as e:
        print(f"  {path}: {e}")

# 5. Verify file presence on server
print("\n[6] Verifying files on server...")
for fname in FRONTEND_FILES:
    result = ssh(f"test -f /var/www/html/{fname} && echo OK || echo MISSING")
    print(f"  /var/www/html/{fname}: {result}")

print("\n✅ Push complete!")


#!/usr/bin/env python3
import paramiko, sys

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

def cmd(c):
    _, o, e = ssh.exec_command(c)
    return o.read().decode().strip()

print("=== Volume mounts ===")
print(cmd("docker inspect anamnezai-backend-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Mode}})\\n{{end}}'"))

print("\n=== patient_dashboard.html - PDL noVisits count ===")
print(cmd("grep -c 'noVisits' /srv/anamnezai/frontend/patient_dashboard.html"))

print("\n=== index.html - bg-pric on lang buttons? ===")
r = cmd("grep -n 'btn-tr.*bg-pric\\|btn-en.*bg-pric\\|btn-ar.*bg-pric' /srv/anamnezai/frontend/index.html")
print(r if r else "(none - buttons fixed!)")

print("\n=== doctor.html - bg-pric on lang buttons? ===")
r = cmd("grep -n 'dlbtn-tr.*bg-pric\\|dlbtn.*bg-pric' /srv/anamnezai/frontend/doctor.html")
print(r if r else "(none - buttons fixed!)")

print("\n=== admin.html - bg-white on lang buttons? ===")
r = cmd("grep -n 'alng-tr.*bg-white\\|alng.*bg-white' /srv/anamnezai/frontend/admin.html")
print(r if r else "(none - buttons fixed!)")

print("\n=== patient_dashboard.html line count ===")
print(cmd("wc -l /srv/anamnezai/frontend/patient_dashboard.html"))

ssh.close()
print("\n=== Done ===")


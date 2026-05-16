#!/usr/bin/env python3
import paramiko

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

def cmd(c):
    _, o, e = ssh.exec_command(c)
    return o.read().decode().strip()

print("=== CPU ===")
print(cmd("lscpu | grep -E 'Model name|CPU\\(s\\)|Thread' | head -5"))

print("\n=== RAM ===")
print(cmd("free -h | head -2"))

print("\n=== GPU ===")
gpu = cmd("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo '(no nvidia GPU)'")
print(gpu)
amd = cmd("rocm-smi --showmeminfo vram 2>/dev/null || echo '(no AMD GPU)'")
if "no AMD" not in amd:
    print(amd)

print("\n=== Ollama model + current load ===")
print(cmd("docker exec anamnezai-backend-1 curl -s http://10.200.9.11:11434/api/tags 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(m['name'], m.get('size',0)//1024//1024, 'MB') for m in d.get('models',[])]\" 2>/dev/null || echo 'could not reach ollama from container'"))

print("\n=== Ollama running models (loaded in VRAM) ===")
print(cmd("curl -s http://10.200.9.11:11434/api/ps 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(m['name'], 'size_vram:', m.get('size_vram',0)//1024//1024, 'MB') for m in d.get('models',[])]\" 2>/dev/null || echo 'N/A'"))

print("\n=== OLLAMA_BASE_URL in container ===")
print(cmd("docker exec anamnezai-backend-1 env | grep OLLAMA 2>/dev/null"))

ssh.close()


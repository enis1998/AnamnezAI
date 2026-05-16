#!/usr/bin/env python3
"""GPU hız testi - sunucu üzerinden gerçek inference"""
import paramiko, time, json, sys

HOST = "10.200.9.11"
USER = "root"
PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)

def cmd(c, timeout=120):
    chan = ssh.get_transport().open_session()
    chan.exec_command(c)
    chan.settimeout(timeout)
    out = chan.makefile('r').read()
    return out.strip()

# Seans başlat
print("[Test] Seans baslatiliyor...")
t0 = time.time()
out = cmd("curl -sf -X POST http://localhost:8001/api/session/start -H 'Content-Type: application/json' -d '{\"patient_name\":\"Test Hasta\",\"age\":35,\"gender\":\"M\",\"language\":\"tr\"}'")
t1 = time.time()
print(f"  Seans start: {t1-t0:.1f}s")
print(f"  Yanit: {out[:200]}")

data = json.loads(out)
sid = data.get("session_id", "")
q = data.get("question", "")
print(f"  SID: {sid}")
print(f"  Soru: {q}")

if not sid:
    print("HATA: session_id alinamadi")
    ssh.close()
    sys.exit(1)

# Cevap ver (GPU test)
print("\n[Test] Cevap gonderiliyor (GPU inference)...")
body = json.dumps({"session_id": sid, "answer": "Basim agriyor, 3 gundur devam ediyor, bulanti da var"})
body_escaped = body.replace("'", "'\\''")
t2 = time.time()
out2 = cmd(f"curl -sf -X POST http://localhost:8001/api/session/answer -H 'Content-Type: application/json' -d '{body_escaped}'", timeout=120)
t3 = time.time()
gpu_time = t3 - t2

print(f"  GPU inference: {gpu_time:.1f}s")
try:
    d2 = json.loads(out2)
    next_q = d2.get("question") or d2.get("next_question", "")
    print(f"  Sonraki soru: {next_q}")
    print(f"  Done: {d2.get('done', False)}")
except:
    print(f"  Ham yanit: {out2[:300]}")

print(f"\n=== SONUC ===")
print(f"  GPU inference suresi: {gpu_time:.1f} saniye")
if gpu_time < 15:
    print(f"  MUKEMMEL - GPU aktif ve hizli!")
elif gpu_time < 40:
    print(f"  IYI - GPU/CPU mix (model 9.6GB, VRAM 8GB)")
else:
    print(f"  YAVAS - Tunel latency veya CPU fallback?")

ssh.close()






#!/usr/bin/env python3
"""final_test.py — Tüm özellikler final test"""
import paramiko, json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.200.9.11', port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace').strip()
    err = stderr.read().decode('utf-8', 'replace').strip()
    return out or err

BASE = "http://localhost:8001"

print("=" * 65)
print("✅ AnamnezAI — Final Test (Model Hazır!)")
print("=" * 65)

results = {}

# 1. Health
print("\n1. Health check:")
r = run(f"curl -s --max-time 5 '{BASE}/health'")
ok = '"ollama":"connected"' in r
print(f"  {'✅' if ok else '❌'} /health: {r[:120]}")
results['health'] = ok

# 2. Session start (AI çağrısı)
print("\n2. Session start (AI olmayan - hızlı):")
body = '{"patient_name":"Ali Veli","age":45,"gender":"Erkek","language":"tr"}'
r = run(f"curl -s --max-time 10 -X POST '{BASE}/api/session/start' -H 'Content-Type: application/json' -d '{body}'")
try:
    d = json.loads(r)
    sid = d.get('session_id')
    q = d.get('question', '')
    ok = bool(sid and q)
    print(f"  {'✅' if ok else '❌'} Session ID: {sid}")
    print(f"  Soru: {q}")
    results['session_start'] = ok
except Exception as e:
    print(f"  ❌ Hata: {e} | {r[:100]}")
    sid = None
    results['session_start'] = False

# 3. Session answer (Gemma 4 çağrısı)
if sid:
    print("\n3. Session answer (Gemma 4 AI çağrısı):")
    body2 = json.dumps({"session_id": sid, "answer": "sabahtan beri şiddetli baş ağrım var, ateşim de çıktı"})
    r2 = run(f"curl -s --max-time 45 -X POST '{BASE}/api/session/answer' -H 'Content-Type: application/json' -d '{body2}'", timeout=50)
    try:
        d2 = json.loads(r2)
        next_q = d2.get('question', '')
        ok2 = bool(next_q and next_q != '__COMPLETED__')
        print(f"  {'✅' if ok2 else '❌'} Sonraki soru: {next_q[:100]}")
        results['session_answer'] = ok2
    except Exception as e:
        print(f"  ❌ Hata: {e} | {r2[:100]}")
        results['session_answer'] = False

# 4. Channel intake (WhatsApp-style)
print("\n4. Channel intake (WhatsApp-style demo):")
ch_body = '{"channel":"whatsapp_demo","external_user_id":"test-user-final","message":"bas agrim ve ates var","language":"tr"}'
r3 = run(f"curl -s --max-time 45 -X POST '{BASE}/api/channel/intake/message' -H 'Content-Type: application/json' -d '{ch_body}'", timeout=50)
try:
    d3 = json.loads(r3)
    reply = d3.get('reply', '')
    csid = d3.get('session_id', '')
    ok3 = bool(reply and csid)
    print(f"  {'✅' if ok3 else '❌'} Reply: {reply[:100]}")
    print(f"  Session ID: {csid}")
    results['channel_intake'] = ok3
except Exception as e:
    print(f"  ❌ Hata: {e} | {r3[:100]}")
    results['channel_intake'] = False

# 5. Doctor queue
print("\n5. Doctor queue:")
r4 = run(f"curl -s --max-time 5 '{BASE}/api/patients/queue'")
try:
    d4 = json.loads(r4)
    total = d4.get('total', 0)
    stats = d4.get('stats', {})
    ok4 = isinstance(total, int)
    print(f"  {'✅' if ok4 else '❌'} Toplam: {total} hasta | Stats: {stats}")
    results['queue'] = ok4
except Exception as e:
    print(f"  ❌ Hata: {e}")
    results['queue'] = False

# 6. Evaluation
print("\n6. Evaluation dashboard:")
r5 = run(f"curl -s --max-time 5 '{BASE}/api/evaluation'")
ok5 = '"triage_accuracy_pct"' in r5
print(f"  {'✅' if ok5 else '❌'} Evaluation: {r5[:80]}")
results['evaluation'] = ok5

# 7. Statik sayfalar
print("\n7. Kritik statik sayfalar:")
pages = ['index.html', 'landing.html', 'doctor.html', 'admin.html',
         'kiosk.html', 'channel_demo.html', 'robots.txt', 'favicon.ico']
for page in pages:
    code = run(f"curl -sI --max-time 3 '{BASE}/{page}' | head -1")
    ok = '200' in code
    print(f"  {'✅' if ok else '❌'} /{page}: {code[:30]}")
    results[page] = ok

# 8. Özet
print("\n" + "=" * 65)
passed = sum(1 for v in results.values() if v)
total_tests = len(results)
print(f"  TOPLAM: {passed}/{total_tests} test geçti")
for name, ok in results.items():
    print(f"  {'✅' if ok else '❌'} {name}")

client.close()
print("=" * 65)


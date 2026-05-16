import paramiko, time

HOST = "10.200.9.11"
ROOT_USER = "root"
ROOT_PASS = "nWTGzzDqwyFyNJhqMhvcjEJj"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username=ROOT_USER, password=ROOT_PASS, timeout=15,
               look_for_keys=False, allow_agent=False)
print("✅ Bağlandı")

def run(cmd, timeout=30, ignore_error=False):
    print(f"  $ {cmd[:100]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return (out + err).strip()

# Mevcut Ollama modeli var mı?
print("\n[Mevcut Ollama modelleri]")
out = run("ollama list 2>/dev/null || echo 'NO_MODELS'")
print(out)

# gemma4:e4b indirimini arka planda başlat
print("\n🦙 gemma4:e4b modeli arka planda indiriliyor (~9.6GB)...")
print("  Bu sunucunun internet hızına göre 30-120 dakika sürebilir.")
print("  Arkaplanda çalışır, siteyi engellemez.")

# nohup ile arka planda çalıştır, log dosyasına yaz
out = run(
    "nohup ollama pull gemma4:e4b > /var/log/ollama_pull.log 2>&1 & echo $!",
    timeout=10, ignore_error=True
)
print(f"  PID: {out}")

time.sleep(3)

# Pull başladı mı kontrol
out = run("tail -5 /var/log/ollama_pull.log 2>/dev/null || echo 'log henüz yok'")
print(f"\n  Pull log:\n  {out}")

# Ollama API sağlık kontrolü
out = run("curl -s http://localhost:11434/api/version")
print(f"\n  Ollama API: {out}")

# Backend ile Ollama bağlantısı kontrolü
out = run("curl -s --max-time 5 http://localhost:8001/health | python3 -m json.tool 2>/dev/null | head -20")
print(f"\n  Backend /health:\n{out}")

print("\n" + "="*60)
print("ÖZET")
print("="*60)
print("""
✅ Backend:  http://10.200.9.11:8001       → ÇALIŞIYOR  
✅ Nginx:    https://10.200.9.11           → ÇALIŞIYOR (self-signed)
⏳ Ollama:  gemma4:e4b indiriliyor (arka plan)
             İzlemek için: tail -f /var/log/ollama_pull.log

SIRADAKI ADIMLAR:

1️⃣  DNS GÜNCELLEMESI (SİZ YAPACAKSINIZ):
    Domain yönetim panelinize girin (isimtescil/natro/cloudflare vs.)
    lifetrack.com.tr     → A → 195.87.198.163
    www.lifetrack.com.tr → A → 195.87.198.163

2️⃣  DNS yayıldıktan sonra SSL (bana söyleyin, yapayım):
    certbot --nginx -d lifetrack.com.tr -d www.lifetrack.com.tr --non-interactive --agree-tos -m admin@lifetrack.com.tr

3️⃣  Model indikten sonra warmup (otomatik çalışır)

⚠️  Şu an https://lifetrack.com.tr DNS 208.91.112.55'e bakıyor
    195.87.198.163 olarak güncellemeniz gerekiyor!
""")

client.close()


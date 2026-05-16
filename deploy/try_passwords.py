import paramiko
import sys

HOST_LAN = "10.200.9.11"
HOST_WAN = "195.87.198.163"
USER = "root"

# Olası şifre varyasyonları (--- belge formatından gelebilir)
PASSWORDS = [
    "plp2026---",
    "plp2026",
    "plp2026--",
    "plp2026-",
    "plp2026___",
    "PLP2026---",
    "plp2026...",
]

for host in [HOST_LAN, HOST_WAN]:
    print(f"\n=== Host: {host} ===")
    for pw in PASSWORDS:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, port=22, username=USER, password=pw, timeout=6,
                           look_for_keys=False, allow_agent=False)
            print(f"  ✅ BAŞARILI: '{pw}'")
            stdin, stdout, stderr = client.exec_command("echo OK && uname -a")
            print("  " + stdout.read().decode().strip())
            client.close()
            sys.exit(0)
        except paramiko.AuthenticationException:
            print(f"  ❌ '{pw}' -> auth failed")
        except Exception as e:
            print(f"  ⚠  '{pw}' -> {e}")
            break  # host erişilemiyor, sonrakine geç

print("\nHiçbir kombinasyon çalışmadı.")


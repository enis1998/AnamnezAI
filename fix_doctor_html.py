"""
doctor.html içindeki yinelenen (duplicate) DL bloğunu ve eski t() fonksiyonunu siler.
"""

path = r"C:\Users\pc\Desktop\Health\mediscreen\frontend\doctor.html"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Silmek istediğimiz blok:
# "// ── setLang ve diğer dil yardımcıları aşağıda tanımlı ──────────────────────"
# + tüm eski DL içeriği (// Header ... }) + eski t() fonksiyonu
# "function setLang(l){" başladığında dur

# Önce konumları bul
marker_start = "// ── setLang ve diğer dil yardımcıları aşağıda tanımlı ──────────────────────"
marker_end = "function setLang(l){"

start_idx = content.find(marker_start)
end_idx = content.find(marker_end)

if start_idx == -1:
    print("❌ Başlangıç marker bulunamadı!")
    exit(1)

if end_idx == -1:
    print("❌ Bitiş marker bulunamadı!")
    exit(1)

print(f"Silme aralığı: karakter {start_idx} - {end_idx}")
print(f"Silinecek içerik boyutu: {end_idx - start_idx} karakter")

# Silmek istediğimiz bölgedeki içeriği göster (ilk 200 karakter)
sample = content[start_idx:start_idx+200]
print(f"Silinecek başlangıç:\n{repr(sample)}\n")

# Değiştir
new_content = content[:start_idx] + "\n" + content[end_idx:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"✅ Temizlendi! Yeni dosya boyutu: {len(new_content)} karakter")

# Doğrulama
with open(path, 'r', encoding='utf-8') as f:
    verify = f.read()

dl_count = verify.count("const DL = {")
t_count = verify.count("function t(key")
setlang_count = verify.count("function setLang(l)")
print(f"'const DL' sayısı: {dl_count} (1 olmalı)")
print(f"'function t(key' sayısı: {t_count} (1 olmalı)")
print(f"'function setLang' sayısı: {setlang_count} (1 olmalı)")


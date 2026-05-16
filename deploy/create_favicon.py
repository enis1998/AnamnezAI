#!/usr/bin/env python3
"""create_favicon.py — Basit favicon.ico oluştur ve deploy et"""
import struct, os, paramiko

# Minimal 16x16 ICO dosyası oluştur (yeşil artı işareti / sağlık ikonu)
def create_minimal_ico():
    """16x16 piksel basit ICO dosyası — AnamnezAI yeşil rengi (#006a68)"""
    # 16x16 RGBA bitmap — yeşil arka plan, beyaz artı
    width, height = 16, 16
    # Primary color: #006a68 (teal/green - secondary brand color)
    # White cross in center
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            # Köşeleri yuvarlatmak için daire şekli
            cx, cy = x - 7.5, y - 7.5
            in_circle = (cx*cx + cy*cy) <= 60
            # Artı şekli (beyaz)
            in_cross = (3 <= x <= 12 and 7 <= y <= 8) or (7 <= x <= 8 and 3 <= y <= 12)
            if not in_circle:
                row.append((0, 0, 0, 0))  # transparent
            elif in_cross:
                row.append((255, 255, 255, 255))  # white
            else:
                row.append((0, 106, 104, 255))  # #006a68
        pixels.append(row)

    # BMP veri oluştur (aşağıdan yukarı)
    bmp_data = bytearray()
    for row in reversed(pixels):
        for r, g, b, a in row:
            bmp_data.extend([b, g, r, a])  # BGRA

    bmp_size = len(bmp_data)

    # BITMAPINFOHEADER (40 byte)
    bmp_header = struct.pack('<IIIHHIIIIII',
        40,              # biSize
        width,           # biWidth
        height * 2,      # biHeight (x2 = AND + XOR mask)
        1,               # biPlanes
        32,              # biBitCount (RGBA)
        0,               # biCompression
        bmp_size,        # biSizeImage
        0, 0, 0, 0       # biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant
    )

    # AND mask (tümü 0)
    and_mask = bytes(height * (width // 8 + (1 if width % 8 else 0)))

    image_data = bmp_header + bytes(bmp_data) + and_mask

    # ICO header
    # ICONDIR
    ico_header = struct.pack('<HHH', 0, 1, 1)  # reserved, type=1, count=1

    # ICONDIRENTRY
    header_size = 6 + 16  # ICONDIR + ICONDIRENTRY
    ico_entry = struct.pack('<BBBBHHII',
        width,       # bWidth
        height,      # bHeight
        0,           # bColorCount (0 = 256+)
        0,           # bReserved
        1,           # wPlanes
        32,          # wBitCount
        len(image_data),  # dwBytesInRes
        header_size  # dwImageOffset
    )

    return ico_header + ico_entry + image_data

ico_data = create_minimal_ico()
favicon_path = r"C:\Users\pc\Desktop\Health\mediscreen\frontend\favicon.ico"
with open(favicon_path, 'wb') as f:
    f.write(ico_data)
print(f"✅ favicon.ico oluşturuldu: {len(ico_data)} byte")

# Deploy et
HOST = "10.200.9.11"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=22, username='root', password='nWTGzzDqwyFyNJhqMhvcjEJj', timeout=15)
sftp = client.open_sftp()

REMOTE = "/srv/anamnezai"
CONTAINER = "anamnezai-backend-1"

sftp.put(favicon_path, f"{REMOTE}/frontend/favicon.ico")
print("✅ favicon.ico sunucuya yüklendi")

_, stdout, stderr = client.exec_command(
    f"docker cp {REMOTE}/frontend/favicon.ico {CONTAINER}:/app/frontend/favicon.ico"
)
stdout.read(); stderr.read()
print("✅ favicon.ico container'a kopyalandı")

# Kontrol
_, stdout, _ = client.exec_command("curl -sI --max-time 3 http://localhost:8001/favicon.ico | head -1")
status = stdout.read().decode().strip()
print(f"✅ HTTP: {status}")

sftp.close()
client.close()
print("Favicon deploy tamamlandı!")


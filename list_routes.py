import re
with open('backend/main.py', encoding='utf-8') as f:
    content = f.read()

# Tüm API route'ları listele
all_routes = re.findall(r'@app\.(get|post|put|delete)\(["\']([^"\']+)["\']', content)
print("=== All routes ===")
for m in all_routes:
    print(f"  {m[0].upper()} {m[1]}")

# summary ile ilgili route
print("\n=== Summary related routes ===")
for line in content.split('\n'):
    if 'summary' in line.lower() and ('@app.' in line or 'def ' in line):
        print(' ', line.strip())


import sys
sys.stdout.reconfigure(encoding='utf-8')

# Fix clinical_review.html - 4 replacement chars
F = 'frontend/clinical_review.html'
with open(F, 'rb') as f: raw = f.read()
c = raw.decode('utf-8', errors='replace')

# Replace \ufffd with likely intended characters
# Check context of replacement chars
for i, ch in enumerate(c):
    if ch == '\ufffd':
        print(f'  pos {i}: ...{repr(c[max(0,i-15):i+15])}...')


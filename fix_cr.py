import sys
sys.stdout.reconfigure(encoding='utf-8')

F = 'frontend/clinical_review.html'
with open(F, 'rb') as f: raw = f.read()
c = raw.decode('utf-8', errors='replace')
orig = c

# Fix 1: 'İla??lar' → 'İlaçlar' (ç U+00E7)
c = c.replace('İla\ufffd\ufffdlar', 'İlaçlar')
# Fix 2: Arabic 'مع??ومات' → 'معلومات' (ل U+0644)
c = c.replace('مع\ufffd\ufffdومات', 'معلومات')

if c != orig:
    with open(F, 'w', encoding='utf-8', newline='') as f:
        f.write(c)
    print('clinical_review.html FIXED and saved')
else:
    print('No changes')

# Verify
with open(F, 'rb') as f: raw2 = f.read()
ufffd_count = raw2.decode('utf-8','replace').count('\ufffd')
print(f'Remaining ufffd: {ufffd_count}')


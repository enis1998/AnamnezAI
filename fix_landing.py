#!/usr/bin/env python3
"""Fix landing.html: repair mojibake encoding + replace remaining MediScreen brand refs."""
import re, sys

path = r"C:\Users\pc\Desktop\Health\mediscreen\frontend\landing.html"

with open(path, 'rb') as f:
    raw = f.read()

# Strip UTF-8 BOM if present
if raw.startswith(b'\xef\xbb\xbf'):
    raw = raw[3:]

# The file was saved as latin-1 but contains UTF-8 byte sequences → fix mojibake
content = raw.decode('latin-1')
try:
    fixed = content.encode('latin-1').decode('utf-8')
    print(f"✅ Mojibake fixed")
except Exception as e:
    print(f"❌ Encoding fix failed: {e}")
    sys.exit(1)

# ── Brand cleanup: replace remaining MediScreen → AnamnezAI ──────────────────
replacements = [
    # nav brand i18n key
    ("'nav.brand':'by MediScreen'",           "'nav.brand':'AnamnezAI Platform'"),
    ('"nav.brand":"by MediScreen"',            '"nav.brand":"AnamnezAI Platform"'),
    # standalone occurrences in JS dicts
    ("MediScreen Platform",                    "AnamnezAI Platform"),
    ("by MediScreen",                          "by AnamnezAI"),
    # any leftover bare brand
    ("MediScreen",                             "AnamnezAI"),
]

for old, new in replacements:
    count = fixed.count(old)
    if count:
        fixed = fixed.replace(old, new)
        print(f"  Replaced {count}x  '{old[:50]}' → '{new[:50]}'")

# Write back as clean UTF-8 (no BOM)
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(fixed)

print(f"\n✅ landing.html saved ({len(fixed)} chars, UTF-8, no BOM)")

# Quick sanity check
remaining = re.findall(r'MediScreen', fixed)
mojibake  = re.findall(r'Ã[^\s]{1}', fixed)
print(f"   Remaining 'MediScreen' occurrences : {len(remaining)}")
print(f"   Remaining mojibake patterns        : {len(mojibake)}")


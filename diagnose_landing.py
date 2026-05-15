#!/usr/bin/env python3
"""Diagnose landing.html encoding state and what needs to be fixed."""
with open(r'C:\Users\pc\Desktop\Health\mediscreen\frontend\landing.html', 'r', encoding='utf-8') as f:
    content = f.read()

non_ascii = [c for c in content if ord(c) > 0x7f]
print(f'Non-ASCII chars count: {len(non_ascii)}')
print(f'Unique non-ASCII chars: {"".join(sorted(set(non_ascii))[:50])}')

# Find loadLandingMetrics
print('Has loadLandingMetrics:', 'loadLandingMetrics' in content)
print('Has MediScreen:', content.count('MediScreen'))

# Find LL dict
idx = content.find("'baslik'")
if idx >= 0:
    print('\nLL dict sample:', repr(content[idx:idx+200]))
else:
    print('\nNo LL dict with baslik found')
    # find any JS dict
    idx2 = content.find("'nav'")
    if idx2 >= 0:
        print('nav dict:', repr(content[idx2:idx2+100]))

# Check what the corrupted title looks like
idx3 = content.find('<title>')
if idx3 >= 0:
    print('\nTitle:', repr(content[idx3:idx3+100]))


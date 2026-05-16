import re, sys
sys.stdout.reconfigure(encoding='utf-8')

F = 'frontend/doctor.html'
with open(F, 'rb') as f: raw = f.read()

# Check line endings
crlf = raw.count(b'\r\n')
lf_only = raw.count(b'\n') - crlf
print('CRLF:', crlf, 'LF-only:', lf_only)

c = raw.decode('utf-8')
orig = c

R='\U0001F534'; Y='\U0001F7E1'; G='\U0001F7E2'
W='\u26a0\ufe0f'; B='\U0001F9E0'; SI='\U0001F6A8'
CL='\u23f0'; CH='\u2705'; HG='\u23f3'
LK='\U0001F512'; UL='\U0001F513'; NE='\U0001F489'

# Fix1: Check forEach pattern with both line endings
# Check what's after the boxShadow line
idx = c.find("el.style.boxShadow = isActive ? '0 0 0 2px #00475e' : '';")
if idx >= 0:
    snippet = repr(c[idx:idx+60])
    print('boxShadow snippet:', snippet)
    # Fix: close forEach
    for old_sep, new_sep in [('\r\n', '\r\n'), ('\n', '\n')]:
        old_pat = "    el.style.boxShadow = isActive ? '0 0 0 2px #00475e' : '';" + old_sep + old_sep + "  // TCFG"
        new_pat = "    el.style.boxShadow = isActive ? '0 0 0 2px #00475e' : '';" + new_sep + "  });" + new_sep + new_sep + "  // TCFG"
        if old_pat in c:
            c = c.replace(old_pat, new_pat, 1)
            print('Fix1 OK (sep:', repr(old_sep),')')
            break
    else:
        print('Fix1 SKIP - checking next chars:', repr(c[idx+57:idx+100]))
else:
    print('Fix1: boxShadow line not found!')

# Fix2: Use regex for remaining ?? patterns with non-ASCII after
# Pattern like: '?? ' followed by any char up to the closing quote
def fix_qq_regex(text, emj, word_pattern):
    pattern = r'\?\? (' + word_pattern + r')'
    return re.sub(pattern, emj + r' \1', text)

# Remaining TR patterns
pairs_re = [
    (CL, r'K[^\'\n]+rede'),    # K?sa S?rede
    (CL, r'K[^\'\n]+sa'),      # K?sa
    (W, r'AI neden[^\'\n]+'),   # AI neden bu triaj? ?nerdi?
    (W, r'Randevuyu[^\'\n]+'),   # Randevuyu Beklememe Uyar?s?
    (UL, r'Kiosk a[^\'\n]+'),    # Kiosk a??ld?
    (Y, r'[^\'\n]+kincil'),      # ?kincil
]
n2 = 0
for emj, pat in pairs_re:
    before = c.count('?? ')
    c = fix_qq_regex(c, emj, pat)
    after = c.count('?? ')
    n2 += (before - after)

# EN remaining
en_pairs_re = [
    (W, r'Why did AI[^\'\n]+'),
]
for emj, pat in en_pairs_re:
    before = c.count('?? ')
    c = fix_qq_regex(c, emj, pat)
    after = c.count('?? ')
    n2 += (before - after)

print('Fix2-extra:', n2)

# Fix3b: gender - find the actual pattern in file
idx_g = c.find("t('ageFn', p.age)}")
if idx_g < 0: idx_g = c.find("ageFn', p.age)")
if idx_g >= 0:
    snippet = repr(c[idx_g:idx_g+60])
    print('gender snippet:', snippet)
    # Replace p.gender (not already localized)
    g_pat = r"\$\{t\('ageFn',\s*p\.age\)\}\s*\u25c6\s*\$\{p\.gender\}"
    m_g = re.search(g_pat, c)
    if m_g:
        old_g = m_g.group(0)
        new_g = old_g.replace('${p.gender}', "${localize(p.gender||'')}")
        c = c.replace(old_g, new_g, 1)
        print('Fix3b OK (regex)')

if c != orig:
    with open(F, 'w', encoding='utf-8') as f: f.write(c)
    print('SAVED')
else:
    print('NOOP')

rem = [(i+1, l.strip()[:90]) for i, l in enumerate(c.split('\n')) if '??' in l and i < 2200]
# Filter out Arabic lines (lines where ?? is part of Arabic words)
non_arabic = [(no, t) for no, t in rem if not all(ord(ch) > 0x0600 or ch in '?? \'"' for ch in t)]
print('Remaining ??(non-Arabic):', len(non_arabic))
for no, t in non_arabic[:15]: print(' ', no, t[:90])
print('Total remaining (incl Arabic):', len(rem))


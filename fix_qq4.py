import sys
sys.stdout.reconfigure(encoding='utf-8')

F = 'frontend/doctor.html'
with open(F, 'rb') as f: raw = f.read()
c = raw.decode('utf-8')
orig = c

# Fix1: forEach - use exact byte sequence found by fix_qq2
# Content: "'';\r\n\r\r\n  // TCFG"
# Insert }); after the boxShadow line
# Confirmed sequence: boxShadow line ends with \r\n, then \r\r\n before // TCFG

old_f1 = "'0 0 0 2px #00475e' : '';\r\n\r\r\n  // TCFG"
new_f1 = "'0 0 0 2px #00475e' : '';\r\n  });\r\n\r\r\n  // TCFG"
if old_f1 in c:
    c = c.replace(old_f1, new_f1, 1)
    print('Fix1 OK')
else:
    # Try other CRLF variations
    variants = [
        ("'0 0 0 2px #00475e' : '';\r\n\r\n  // TCFG",
         "'0 0 0 2px #00475e' : '';\r\n  });\r\n\r\n  // TCFG"),
        ("'0 0 0 2px #00475e' : '';\n\n  // TCFG",
         "'0 0 0 2px #00475e' : '';\n  });\n\n  // TCFG"),
    ]
    for ov, nv in variants:
        if ov in c:
            c = c.replace(ov, nv, 1)
            print('Fix1 OK (variant)')
            break
    else:
        # Show exact bytes around the area
        idx = c.find("'0 0 0 2px #00475e' : '';")
        if idx >= 0:
            print('Fix1 context:', repr(c[idx:idx+80]))
        else:
            print('Fix1 FAIL: pattern not found at all')

# Fix3b: gender - use exact character U+25C6 diamond
DIAMOND = '\u25c6'
old_g = "${t('ageFn', p.age)} " + DIAMOND + " ${p.gender}</p>"
new_g = "${t('ageFn', p.age)} " + DIAMOND + " ${localize(p.gender||'')}</p>"
if old_g in c:
    c = c.replace(old_g, new_g, 1)
    print('Fix3b OK')
else:
    # Search without the diamond
    idx_a = c.find("t('ageFn', p.age)}")
    if idx_a >= 0:
        snippet = repr(c[idx_a: idx_a+60])
        print('Fix3b context:', snippet)
        # Try with a regex using the actual character
        import re
        m = re.search(r"\$\{t\('ageFn', p\.age\)\} . \$\{p\.gender\}", c)
        if m:
            old_ = m.group(0)
            new_ = old_.replace("${p.gender}", "${localize(p.gender||'')}")
            c = c.replace(old_, new_, 1)
            print('Fix3b OK (dot-match)')
        else:
            print('Fix3b SKIP')

if c != orig:
    with open(F, 'w', encoding='utf-8') as f: f.write(c)
    print('SAVED')
else:
    print('NOOP')

# Verify Fix1: check that }); is present after boxShadow
if "boxShadow = isActive ? '0 0 0 2px #00475e' : '';" in c:
    idx = c.find("boxShadow = isActive ? '0 0 0 2px #00475e' : '';")
    after = repr(c[idx:idx+60])
    print('Fix1 verify:', after)

# Verify Fix3b
if 'localize(p.gender' in c:
    print('Fix3b verify: localize(p.gender found')
else:
    print('Fix3b verify: MISSING!')


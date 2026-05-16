import sys
sys.stdout.reconfigure(encoding='utf-8')

F = 'frontend/doctor.html'
with open(F, 'rb') as f: raw = f.read()
c = raw.decode('utf-8')
orig = c

# Fix1: forEach - exact sequence: \r\r\r\n\r\r\r\r\n = multiple corrupt CRs
old_f1 = "'0 0 0 2px #00475e' : '';\r\r\r\n\r\r\r\r\n  // TCFG"
new_f1 = "'0 0 0 2px #00475e' : '';\r\n  });\r\n\r\n  // TCFG"
if old_f1 in c:
    c = c.replace(old_f1, new_f1, 1)
    print('Fix1 OK')
else:
    # Try to locate and show bytes
    import re
    m = re.search(r"'0 0 0 2px #00475e' : '';\r+\n\r+\n  // TCFG", c)
    if m:
        old = m.group(0)
        new = "'0 0 0 2px #00475e' : '';\r\n  });\r\n\r\n  // TCFG"
        c = c.replace(old, new, 1)
        print('Fix1 OK (regex variant)')
    else:
        print('Fix1 FAIL:', repr(c[c.find("0 2px #00475e'")-5:c.find("0 2px #00475e'")+80]))

if c != orig:
    with open(F, 'w', encoding='utf-8') as f: f.write(c)
    print('SAVED')
else:
    print('NOOP')

# Verify
idx = c.find("boxShadow = isActive ? '0 0 0 2px #00475e' : '';")
print('Fix1 verify:', repr(c[idx:idx+60]))
print('localize(p.gender):', 'localize(p.gender' in c)


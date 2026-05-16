import re, sys
sys.stdout.reconfigure(encoding='utf-8')

F = 'frontend/doctor.html'
with open(F, 'rb') as f: raw = f.read()
c = raw.decode('utf-8')
orig = c

R='\U0001F534'; Y='\U0001F7E1'; G='\U0001F7E2'
W='\u26a0\ufe0f'; B='\U0001F9E0'; SI='\U0001F6A8'
CL='\u23f0'; CH='\u2705'; HG='\u23f3'
LK='\U0001F512'; UL='\U0001F513'

# Fix1: forEach missing }); - use regex to handle CRLF variations
pat1 = r"(    el\.style\.boxShadow = isActive \? '0 0 0 2px #00475e' : '';)(\r?\n[\r\n]*)(  // TCFG)"
m1 = re.search(pat1, c)
if m1:
    c = re.sub(pat1, r'\1\2  });\2\3', c, count=1)
    # Check if }); was added
    if '  });\r\n' in c or '  });\n' in c:
        print('Fix1 OK')
    else: print('Fix1: sub done, verify manually')
else:
    print('Fix1 SKIP: no match')

# Fix3b: gender using regex
def fix_gender(text):
    # Match: ${t('ageFn', p.age)} ◆ ${p.gender}   (with ◆ = U+25C6)
    pat = r"\$\{t\('ageFn',\s*p\.age\)\}\s*\u25c6\s*\$\{p\.gender\}"
    def repl(m): return m.group(0).replace("${p.gender}", "${localize(p.gender||'')}")
    new_text, n = re.subn(pat, repl, text, count=1)
    return new_text, n

c, n_g = fix_gender(c)
if n_g: print('Fix3b OK:', n_g)
else: print('Fix3b SKIP')

# Fix AR dict emojis - target by key name + arabic content
# Pattern: keyName:'?? [non-ascii]+'
ar_keys = [
    ('statRedLbl', R), ('filterRed', R),
    ('statYellowLbl', Y), ('filterYellow', Y),
    ('statGreenLbl', G), ('filterGreen', G),
    ('detailUrgentTitle', W),
    ('kanbanRed', SI), ('kanbanYellow', CL), ('kanbanGreen', CH), ('kanbanPending', HG),
    ('kioskLocked', LK), ('kioskUnlocked', UL),
    ('pvBriefWarnTitle', W),
    ('queueEmpty', '\U0001F4CB'), ('queueEmptyDemo', '\U0001F4CB'),
    ('queueBackendOff', '\U0001F4E1'),
    ('detailAIReasonTitle', B),
]
n_ar = 0
for key, emj in ar_keys:
    # Replace key:'?? ...
    pat = key + r":'[?][?] "
    def make_repl(e):
        def repl(m): return m.group(0).replace("'?? ", "'" + e + " ")
        return repl
    new_c, n = re.subn(pat, make_repl(emj), c)
    c = new_c
    n_ar += n

print('Fix AR:', n_ar, 'replacements')

if c != orig:
    with open(F, 'w', encoding='utf-8') as f: f.write(c)
    print('SAVED')
else: print('NOOP')

rem = [(i+1, l.strip()[:90]) for i, l in enumerate(c.split('\n')) if '??' in l and i < 2200]
print('Total remaining ?? lines:', len(rem))
# Show non-arabic ones
for no, t in rem[:20]: print(' ', no, t[:90])


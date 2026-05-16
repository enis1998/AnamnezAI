import sys, subprocess, re, os
sys.stdout.reconfigure(encoding='utf-8')

CLEAN_COMMIT = 'd55e186'
OUT_FILE = 'frontend/doctor.html'

# 1. Get clean version from git
print('Step 1: Getting clean base from git...')
result = subprocess.run(
    ['git', 'show', f'{CLEAN_COMMIT}:frontend/doctor.html'],
    capture_output=True
)
if result.returncode != 0:
    print('ERROR getting git content:', result.stderr.decode())
    sys.exit(1)

# Decode the clean content
raw = result.stdout
c = raw.decode('utf-8')
print(f'  Base size: {len(c)} chars, extra_cr: {c.count(chr(13)+chr(13))}')

R='\U0001F534'; Y='\U0001F7E1'; G='\U0001F7E2'
W='\u26a0\ufe0f'; B='\U0001F9E0'; SI='\U0001F6A8'
CL='\u23f0'; CH='\u2705'; HG='\u23f3'
LK='\U0001F512'; UL='\U0001F513'; NE='\U0001F489'

# 2. Fix forEach missing });
print('Step 2: Fix forEach...')
old1 = "    el.style.boxShadow = isActive ? '0 0 0 2px #00475e' : '';\n\n  // TCFG"
new1 = "    el.style.boxShadow = isActive ? '0 0 0 2px #00475e' : '';\n  });\n\n  // TCFG"
if old1 in c:
    c = c.replace(old1, new1, 1)
    print('  OK: forEach fixed')
else:
    print('  SKIP: pattern not found')

# 3. Replace ?? emojis
print('Step 3: Fix ?? emojis...')
words = [
    (SI,'Immediate'),(W,'Urgent Warnings'),(W,'Do Not Wait'),(W,'AI output is advisory'),
    (Y,'Urgent/Can Wait'),(Y,'Acil/Bekleyebilir'),(G,'Routine Queue'),(G,'Rutin Kuyruk'),
    (R,'Emergency'),(Y,'Urgent'),(G,'Routine'),(R,'Acil'),(G,'Rutin'),
    (SI,'Derhal'),(CL,'Shortly'),(HG,'Awaiting Analysis'),(LK,'Kiosk locked'),(UL,'Kiosk unlocked'),(LK,'Kiosk kilitlendi'),
    (W,'Why did AI'),
]
n=0
for emj,w in words:
    if '?? '+w in c:
        c=c.replace('?? '+w, emj+' '+w)
        n+=1
for emj,w in [(NE,'Allergies'),(NE,'Alerjiler')]:
    if w+' ??' in c:
        c=c.replace(w+' ??', w+' '+emj); n+=1
# AR dict labels
ar_keys = [
    ('statRedLbl',R),('filterRed',R),('statYellowLbl',Y),('filterYellow',Y),
    ('statGreenLbl',G),('filterGreen',G),('detailUrgentTitle',W),
    ('kanbanRed',SI),('kanbanYellow',CL),('kanbanGreen',CH),('kanbanPending',HG),
    ('kioskLocked',LK),('kioskUnlocked',UL),('pvBriefWarnTitle',W),
    ('queueEmpty','\U0001F4CB'),('queueEmptyDemo','\U0001F4CB'),('queueBackendOff','\U0001F4E1'),
    ('detailAIReasonTitle',B),
]
for key, emj in ar_keys:
    pattern = key + r":'[?][?] "
    def make_repl(e):
        def repl(m): return m.group(0).replace("'?? ", "'"+e+" ")
        return repl
    new_c, cnt = re.subn(pattern, make_repl(emj), c)
    c = new_c; n += cnt
print(f'  OK: {n} emoji replacements')

# 4. Fix chief_complaint in renderTable
print('Step 4: Fix renderTable chief_complaint...')
m = re.search(r'<td class="px-4 py-3\.5 text-\[12px\] text-ons max-w-\[180px\] truncate">\$\{p\.chief_complaint\|\|[^}]+\}</td>', c)
if m:
    c = c.replace(m.group(0), '<td class="px-4 py-3.5 text-[12px] text-ons max-w-[180px] truncate">${localize(extractText(p.chief_complaint))||\'—\'}</td>', 1)
    print('  OK: chief_complaint wrapped')
else:
    print('  SKIP: td pattern not found')

# 5. Fix gender in renderTable
print('Step 5: Fix gender localize...')
DIAMOND = '\u25c6'
old_g = "${t('ageFn', p.age)} " + DIAMOND + " ${p.gender}</p>"
new_g = "${t('ageFn', p.age)} " + DIAMOND + " ${localize(p.gender||'')}</p>"
if old_g in c:
    c = c.replace(old_g, new_g, 1)
    print('  OK: gender wrapped')
else:
    # Fallback: regex dot match
    m_g = re.search(r"\$\{t\('ageFn', p\.age\)\} . \$\{p\.gender\}", c)
    if m_g:
        replacement = m_g.group(0).replace("${p.gender}", "${localize(p.gender||'')}")
        c = c.replace(m_g.group(0), replacement, 1)
        print('  OK: gender wrapped (regex fallback)')
    else:
        print('  SKIP: gender pattern not found')

# 6. Fix bare p.chief_complaint in cards/kanban
print('Step 6: Fix bare chief_complaint usages...')
bare_fixes = 0
for old_c_str, new_c_str in [
    ("${p.chief_complaint || '—'}", "${localize(extractText(p.chief_complaint))||'—'}"),
    ("${p.chief_complaint}", "${localize(extractText(p.chief_complaint))||'—'}"),
]:
    cnt = c.count(old_c_str)
    if cnt:
        c = c.replace(old_c_str, new_c_str)
        bare_fixes += cnt
print(f'  OK: {bare_fixes} bare usages fixed')

# 7. Write output with proper line endings (CRLF like original)
print('Step 7: Writing...')
with open(OUT_FILE, 'w', encoding='utf-8', newline='') as f:
    f.write(c)
print(f'  OK: written {len(c)} chars')

# Verify
with open(OUT_FILE, 'rb') as f: raw2 = f.read()
c2 = raw2.decode('utf-8')
extra_cr = c2.count('\r\r')
ufffd = c2.count('\ufffd')
qq_remain = sum(1 for line in c2.split('\n') if '?? ' in line and not any(ord(ch)>0x0600 for ch in line))
print(f'\nVerification:')
print(f'  extra_cr: {extra_cr}')
print(f'  ufffd (replacement): {ufffd}')
print(f'  remaining ?? (non-Arabic): {qq_remain}')
print(f'  localize(p.gender): {"OK" if "localize(p.gender" in c2 else "MISSING"}')
fe_ok = "});" in c2 and "// TCFG" in c2
print(f'  forEach close: {"OK" if fe_ok else "CHECK"}')
print(f'  extractText(p.chief): {"OK" if "localize(extractText(p.chief_complaint))" in c2 else "MISSING"}')



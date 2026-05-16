import re, sys
sys.stdout.reconfigure(encoding='utf-8')

F = 'frontend/doctor.html'
with open(F, 'rb') as f: raw = f.read()
try:
    c = raw.decode('utf-8'); enc='utf-8'
except:
    c = raw.decode('latin-1'); enc='latin-1'
print('enc:', enc)
orig = c

R='\U0001F534'; Y='\U0001F7E1'; G='\U0001F7E2'
W='\u26a0\ufe0f'; B='\U0001F9E0'; SI='\U0001F6A8'
CL='\u23f0'; CH='\u2705'; HG='\u23f3'
LK='\U0001F512'; UL='\U0001F513'; NE='\U0001F489'

# Fix1: forEach missing });
a='    el.style.boxShadow = isActive ? \'0 0 0 2px #00475e\' : \'\';\n\n  // TCFG'
b='    el.style.boxShadow = isActive ? \'0 0 0 2px #00475e\' : \'\';\n  });\n\n  // TCFG'
if a in c:
    c=c.replace(a,b,1); print('Fix1 OK')
else: print('Fix1 SKIP')

# Fix2: Replace ?? prefix
words=[(SI,'Immediate'),(W,'Urgent Warnings'),(W,'Do Not Wait'),(W,'AI output is advisory'),
       (Y,'Urgent/Can Wait'),(Y,'Acil/Bekleyebilir'),(G,'Routine Queue'),(G,'Rutin Kuyruk'),
       (R,'Emergency'),(Y,'Urgent'),(G,'Routine'),(R,'Acil'),(G,'Rutin'),
       (SI,'Derhal'),(CL,'Shortly'),(HG,'Awaiting Analysis'),(LK,'Kiosk locked'),(UL,'Kiosk unlocked'),(LK,'Kiosk kilitlendi')]
n=0
for emj,w in words:
    k='?? '+w
    if k in c: c=c.replace(k,emj+' '+w); n+=1
for emj,w in [(NE,'Allergies'),(NE,'Alerjiler')]:
    k=w+' ??'
    if k in c: c=c.replace(k,w+' '+emj); n+=1
print('Fix2:',n)

# Fix3a: chief_complaint in renderTable td
m=re.search(r'<td class="px-4 py-3\.5 text-\[12px\] text-ons max-w-\[180px\] truncate">\$\{p\.chief_complaint\|\|[^}]+\}</td>',c)
if m:
    c=c.replace(m.group(0),'<td class="px-4 py-3.5 text-[12px] text-ons max-w-[180px] truncate">${localize(extractText(p.chief_complaint))||\'-\'}</td>',1)
    print('Fix3a OK')
else: print('Fix3a SKIP')

# Fix3b: gender in renderTable
G3_OLD = "${t('ageFn', p.age)} \u25c6 ${p.gender}</p>"
G3_NEW = "${t('ageFn', p.age)} \u25c6 ${localize(p.gender||'')}</p>"
if G3_OLD in c: c=c.replace(G3_OLD,G3_NEW,1); print('Fix3b OK')
else: print('Fix3b SKIP')

# Fix4: bare chief_complaint
for old,new in [
    ("${p.chief_complaint}", "${localize(extractText(p.chief_complaint))||'-'}"),
]:
    cnt=c.count(old)
    if cnt: c=c.replace(old,new); print('Fix4:',cnt,'x')

if c!=orig:
    with open(F,'w',encoding='utf-8') as f: f.write(c)
    print('SAVED')
else: print('NOOP')

rem=[(i+1,l.strip()[:80]) for i,l in enumerate(c.split('\n')) if '??' in l and i<2200]
print('Remaining:',len(rem))
for no,t in rem[:10]: print(' ',no,t)


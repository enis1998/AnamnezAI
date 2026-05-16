import sys, os
sys.stdout.reconfigure(encoding='utf-8')

# Check all HTML files for encoding issues
HTML_DIR = 'frontend'
BACKEND_DIR = 'backend'

print('=== HTML files encoding check ===')
issues = []
for fname in os.listdir(HTML_DIR):
    if not fname.endswith('.html'): continue
    fpath = os.path.join(HTML_DIR, fname)
    with open(fpath, 'rb') as f: raw = f.read()

    # Check if valid UTF-8
    try:
        content = raw.decode('utf-8')
        # Check for CRLF issues (extra \r)
        extra_cr = content.count('\r\r')
        # Check for mojibake patterns (UTF-8 bytes of Turkish chars interpreted wrong)
        # e.g. Ã¼ = ü, Ã± = ñ, etc.
        mojibake = content.count('\xc3\xbc') + content.count('Ã¼') + content.count('Ã±')
        bad_sequences = content.count('\ufffd')
        crlf_count = content.count('\r\n')

        if extra_cr > 0 or bad_sequences > 0:
            issues.append((fname, 'extra_cr=' + str(extra_cr), 'replacement_chars=' + str(bad_sequences), 'crlf=' + str(crlf_count)))
            print(f'  [{fname}] ISSUES: extra_cr={extra_cr}, replacement={bad_sequences}')
        else:
            print(f'  [{fname}] OK (crlf={crlf_count})')
    except UnicodeDecodeError as e:
        print(f'  [{fname}] NOT UTF-8: {e}')
        issues.append((fname, 'not_utf8'))

print('\n=== Backend main.py check ===')
with open(os.path.join(BACKEND_DIR, 'main.py'), 'rb') as f:
    raw = f.read()
try:
    content = raw.decode('utf-8')
    extra_cr = content.count('\r\r')
    bad = content.count('\ufffd')
    print(f'  main.py: OK, extra_cr={extra_cr}, replacement={bad}')
except Exception as e:
    print(f'  main.py: ERROR {e}')

print('\n=== Files that need fixing ===')
for item in issues:
    print(' ', item)


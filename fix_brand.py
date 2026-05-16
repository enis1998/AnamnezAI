"""Fix MediScreen brand references in frontend files"""
import os, re

base = os.path.dirname(__file__)

# Fix landing.html - read, replace all MediScreen, write back
path = os.path.join(base, 'frontend', 'landing.html')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all remaining MediScreen variants
content = content.replace('MediScreen', 'AnamnezAI')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

remaining = content.count('MediScreen')
print(f'landing.html: {remaining} MediScreen occurrences remaining')

# Fix summary.html PDF header
summary_path = os.path.join(base, 'frontend', 'summary.html')
if os.path.exists(summary_path):
    with open(summary_path, 'r', encoding='utf-8') as f:
        sc = f.read()
    sc = sc.replace('by MediScreen', 'by AnamnezAI')
    sc = sc.replace('MediScreen Sağlık', 'AnamnezAI')
    sc = sc.replace('MediScreen', 'AnamnezAI')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(sc)
    print('summary.html: fixed')

print('Done.')

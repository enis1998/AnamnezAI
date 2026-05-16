#!/usr/bin/env python3
"""
1. Restore landing.html from git HEAD (clean UTF-8)
2. Apply needed changes in Python (no PowerShell encoding risk):
   - MediScreen → AnamnezAI brand replacements
   - Add loadLandingMetrics() function
"""
import subprocess, re

GIT_FILE = r"C:\Users\pc\Desktop\Health\mediscreen\frontend\landing.html"

# ── 1. Get clean version from git ────────────────────────────────────────────
result = subprocess.run(
    ["git", "show", "HEAD:frontend/landing.html"],
    capture_output=True,
    cwd=r"C:\Users\pc\Desktop\Health\mediscreen"
)
if result.returncode != 0:
    print("❌ git show failed:", result.stderr.decode())
    raise SystemExit(1)

content = result.stdout.decode('utf-8')
print(f"✅ Restored from git HEAD ({len(content)} chars)")

# ── 2. Brand cleanup ──────────────────────────────────────────────────────────
brand_map = [
    ("MediScreen Platform",  "AnamnezAI Platform"),
    ("by MediScreen",        "by AnamnezAI"),
    ("MediScreen",           "AnamnezAI"),
]
for old, new in brand_map:
    n = content.count(old)
    if n:
        content = content.replace(old, new)
        print(f"  Replaced {n}×  {old!r} → {new!r}")

# ── 3. Add loadLandingMetrics IIFE before </script> ───────────────────────────
METRICS_JS = r"""
// ── Dynamic landing metrics from evaluation results ──
(async function loadLandingMetrics() {
  try {
    const r = await fetch('/api/public/landing-metrics', {signal: AbortSignal.timeout(5000)});
    if (!r.ok) return;
    const resp = await r.json();
    const d = resp.metrics || resp;
    const update = (sel, val, suffix='') => {
      const el = document.querySelector(sel);
      if (el && val !== undefined) { el.textContent = val + suffix; el.dataset.target = val; }
    };
    if (d.triage_accuracy_pct) update('[data-target="86"]', Math.round(d.triage_accuracy_pct));
    if (d.cases_processed)     update('[data-target="500"]', d.cases_processed + '+');
    if (d.avg_session_min)     update('[data-target="5"]',  d.avg_session_min);
    if (d.medgemma_score)      update('[data-target="4.6"]', d.medgemma_score.toFixed(1));
  } catch(e) { console.debug('[landing] Metrics fetch skipped:', e.message); }
})();
"""

if 'loadLandingMetrics' in content:
    print("  loadLandingMetrics already present — skipping insertion")
else:
    # Insert before the last </script> tag
    last_script_close = content.rfind('</script>')
    if last_script_close >= 0:
        content = content[:last_script_close] + METRICS_JS + content[last_script_close:]
        print("  ✅ Inserted loadLandingMetrics IIFE")
    else:
        print("  ❌ Could not find </script> to insert metrics function")

# ── 4. Write back as clean UTF-8 (no BOM) ────────────────────────────────────
with open(GIT_FILE, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print(f"\n✅ landing.html saved ({len(content)} chars, clean UTF-8)")

# Sanity checks
print(f"   MediScreen remaining : {content.count('MediScreen')}")
print(f"   loadLandingMetrics   : {'loadLandingMetrics' in content}")
# Check Turkish charset integrity (title)
idx = content.find('<title>')
if idx >= 0:
    print(f"   Title: {content[idx:idx+80]}")
# Check for mojibake artifacts
mojibake = re.findall(r'[ÃÂ][^\s]{1}', content)
print(f"   Mojibake artefacts   : {len(mojibake)}")


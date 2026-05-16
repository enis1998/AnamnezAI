#!/usr/bin/env python3
"""Fix i18n for clinical_review.html and summary.html + add inherited lang support."""
import os, re

FRONTEND = r"C:\Users\pc\Desktop\Health\mediscreen\frontend"

# ─── CLINICAL REVIEW ─────────────────────────────────────────────────────────
print("=== clinical_review.html ===")
with open(os.path.join(FRONTEND, "clinical_review.html"), encoding="utf-8") as f:
    html = f.read()

# 1. Add IDs to nav buttons
html = html.replace(
    '<span class="hidden sm:inline">Yazdır</span>',
    '<span id="cr-btn-print" class="hidden sm:inline">Yazdır</span>'
)
html = html.replace(
    '<span class="hidden sm:inline">PDF İndir</span>',
    '<span id="cr-btn-pdf" class="hidden sm:inline">PDF İndir</span>'
)
html = html.replace(
    '<span class="hidden sm:inline">Panele Dön</span>',
    '<span id="cr-btn-back" class="hidden sm:inline">Panele Dön</span>'
)
# Sidebar nav
html = html.replace(
    ' Panel\n      </a>',
    ' <span id="cr-nav-panel">Panel</span>\n      </a>'
)
html = html.replace(
    ' Hasta Kaydı\n      </a>',
    ' <span id="cr-nav-record">Hasta Kaydı</span>\n      </a>'
)
html = html.replace(
    ' Analitik\n      </a>',
    ' <span id="cr-nav-analytics">Analitik</span>\n      </a>'
)
html = html.replace(
    ' Çıkış\n      </button>',
    ' <span id="cr-nav-logout">Çıkış</span>\n      </button>'
)
# Loading/error states
html = html.replace(
    '<p class="text-onsv text-sm">Hasta kaydı yükleniyor...</p>',
    '<p id="cr-loading-txt" class="text-onsv text-sm">Hasta kaydı yükleniyor...</p>'
)
html = html.replace(
    '<p class="text-ons font-semibold">Kayıt bulunamadı</p>',
    '<p id="cr-error-txt" class="text-ons font-semibold">Kayıt bulunamadı</p>'
)
html = html.replace(
    '<a href="doctor.html" class="px-4 py-2 rounded-lg bg-pri text-white text-sm">Panele Dön</a>',
    '<a href="doctor.html" id="cr-error-back" class="px-4 py-2 rounded-lg bg-pri text-white text-sm">Panele Dön</a>'
)
# Content section headers
html = html.replace(
    '<h1 class="text-3xl font-bold text-ons tracking-tight mb-1">Klinik İnceleme Raporu</h1>',
    '<h1 id="cr-page-title" class="text-3xl font-bold text-ons tracking-tight mb-1">Klinik İnceleme Raporu</h1>'
)
html = html.replace(
    'YZ ANALİZİ TAMAMLANDI',
    '<span id="cr-ai-badge">YZ ANALİZİ TAMAMLANDI</span>'
)
html = html.replace(
    '<h2 class="text-xl font-bold text-ons">Klinik YZ Özeti</h2>',
    '<h2 id="cr-summary-title" class="text-xl font-bold text-ons">Klinik YZ Özeti</h2>'
)
html = html.replace(
    '"Yükleniyor..."',
    '"<span id=\'cr-complaint-loading\'>Yükleniyor...</span>"'
)

print("  ✓ Added IDs to nav and section elements")

# 2. Add i18n init script before closing </script> in the main script block
i18n_init = """
// ── i18n: inherit language from localStorage ─────────────────────────────────
const CR_DICT = {
  tr: {
    btnPrint:'Yazdır', btnPdf:'PDF İndir', btnBack:'Panele Dön',
    navPanel:'Panel', navRecord:'Hasta Kaydı', navAnalytics:'Analitik', navLogout:'Çıkış',
    loadingTxt:'Hasta kaydı yükleniyor...', errorTxt:'Kayıt bulunamadı', errorBack:'Panele Dön',
    pageTitle:'Klinik İnceleme Raporu', aiBadge:'YZ ANALİZİ TAMAMLANDI',
    summaryTitle:'Klinik YZ Özeti', aiConfLabel:'YZ Güven Skoru',
    triageLabel:{RED:'🔴 KIRMIZI', YELLOW:'🟡 SARI', GREEN:'🟢 YEŞİL'},
    noUrgencyFlags:'Acil bayrak yok',
    patientQuoteLbl:'Hasta cevabı',
    allInfoPresent:'Tüm bilgiler mevcut',
    docDefault:'Yükleniyor...',
    sectionNotes:'Klinik Notlar', saveNote:'Notu Kaydet',
  },
  en: {
    btnPrint:'Print', btnPdf:'Download PDF', btnBack:'Back to Panel',
    navPanel:'Panel', navRecord:'Patient Record', navAnalytics:'Analytics', navLogout:'Logout',
    loadingTxt:'Loading patient record...', errorTxt:'Record not found', errorBack:'Back to Panel',
    pageTitle:'Clinical Review Report', aiBadge:'AI ANALYSIS COMPLETE',
    summaryTitle:'Clinical AI Summary', aiConfLabel:'AI Confidence Score',
    triageLabel:{RED:'🔴 RED', YELLOW:'🟡 YELLOW', GREEN:'🟢 GREEN'},
    noUrgencyFlags:'No urgent flags',
    patientQuoteLbl:'Patient answer',
    allInfoPresent:'All information present',
    docDefault:'Loading...',
    sectionNotes:'Clinical Notes', saveNote:'Save Note',
  },
  ar: {
    btnPrint:'طباعة', btnPdf:'تنزيل PDF', btnBack:'العودة للوحة',
    navPanel:'اللوحة', navRecord:'سجل المريض', navAnalytics:'التحليلات', navLogout:'تسجيل الخروج',
    loadingTxt:'جارٍ تحميل سجل المريض...', errorTxt:'السجل غير موجود', errorBack:'العودة للوحة',
    pageTitle:'تقرير المراجعة السريرية', aiBadge:'اكتمل التحليل الذكي',
    summaryTitle:'ملخص الذكاء الاصطناعي السريري', aiConfLabel:'درجة ثقة الذكاء',
    triageLabel:{RED:'🔴 أحمر', YELLOW:'🟡 أصفر', GREEN:'🟢 أخضر'},
    noUrgencyFlags:'لا توجد إشارات إلحاح',
    patientQuoteLbl:'إجابة المريض',
    allInfoPresent:'جميع المعلومات متوفرة',
    docDefault:'جارٍ التحميل...',
    sectionNotes:'الملاحظات السريرية', saveNote:'حفظ الملاحظة',
  },
};
const crLang = localStorage.getItem('ui_lang') || 'tr';
function crT(key) { return (CR_DICT[crLang] || CR_DICT.tr)[key] || key; }
function applyCRLang() {
  document.documentElement.lang = crLang;
  document.documentElement.dir = crLang === 'ar' ? 'rtl' : 'ltr';
  const m = {
    'cr-btn-print': crT('btnPrint'), 'cr-btn-pdf': crT('btnPdf'),
    'cr-btn-back': crT('btnBack'), 'cr-error-back': crT('errorBack'),
    'cr-nav-panel': crT('navPanel'), 'cr-nav-record': crT('navRecord'),
    'cr-nav-analytics': crT('navAnalytics'), 'cr-nav-logout': crT('navLogout'),
    'cr-loading-txt': crT('loadingTxt'), 'cr-error-txt': crT('errorTxt'),
    'cr-page-title': crT('pageTitle'), 'cr-ai-badge': crT('aiBadge'),
    'cr-summary-title': crT('summaryTitle'),
  };
  Object.entries(m).forEach(([id, val]) => {
    const el = document.getElementById(id); if (el) el.textContent = val;
  });
}
(function(){ applyCRLang(); })();
"""

# Insert before the last </script> in the file
last_script_end = html.rfind('</script>')
if last_script_end >= 0:
    html = html[:last_script_end] + i18n_init + '\n' + html[last_script_end:]
    print("  ✓ Added CR_DICT + applyCRLang()")
else:
    print("  ✗ No </script> found")

# 3. Fix renderPage triage labels to use crT()
html = html.replace(
    "badge.textContent = { RED: '🔴 KIRMIZI', YELLOW: '🟡 SARI', GREEN: '🟢 YEŞİL' }[tl] || tl;",
    "badge.textContent = ((CR_DICT[crLang]||CR_DICT.tr).triageLabel[tl]) || tl;"
)
html = html.replace(
    "} else { uf.textContent = 'Acil bayrak yok'; }",
    "} else { uf.textContent = crT('noUrgencyFlags'); }"
)

# Fix "Hasta cevabı" label in evidence map
html = html.replace(
    "<p class=\"text-[9px] font-bold text-onsv uppercase tracking-widest mb-1\">Hasta cevabı</p>",
    "<p class=\"text-[9px] font-bold text-onsv uppercase tracking-widest mb-1\">${crT('patientQuoteLbl')}</p>"
)
html = html.replace(
    "? '<span class=\"text-sec text-xs\">Tüm bilgiler mevcut</span>'",
    "? `<span class=\"text-sec text-xs\">${crT('allInfoPresent')}</span>`"
)

print("  ✓ Fixed triage labels and content strings")

with open(os.path.join(FRONTEND, "clinical_review.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("  Saved clinical_review.html")


# ─── SUMMARY.HTML ─────────────────────────────────────────────────────────────
print("\n=== summary.html ===")
with open(os.path.join(FRONTEND, "summary.html"), encoding="utf-8") as f:
    html = f.read()

# Find the nav header
navEnd = html.find('</header>')

# Check nav content
navSection = html[:navEnd+10] if navEnd > 0 else html[:2000]
print(f"  Nav section ({len(navSection)} chars)")

# Find Turkish nav strings
tr_nav = re.findall(r'<span[^>]*>((?:Yazdır|PDF|Rapor|Panele|İndir|Çıkış|Geri)[^<]{0,30})</span>', navSection)
print(f"  Turkish nav items: {tr_nav}")

# Add IDs to summary nav buttons
for old, new_id, tr_txt in [
    ('>Yazdır<', 'sm-btn-print', 'Yazdır'),
    ('>PDF İndir<', 'sm-btn-pdf', 'PDF İndir'),
    ('>Panele Dön<', 'sm-btn-back', 'Panele Dön'),
    ('>Geri Dön<', 'sm-btn-back', 'Geri Dön'),
]:
    if old in html:
        html = html.replace(old, f'><span id="{new_id}">{tr_txt}</span><', 1)
        print(f"  ✓ Added ID to: {tr_txt}")

# Also look for button text patterns
# Yazdır button
html = re.sub(
    r'(<span[^>]*hidden sm:inline[^>]*>)Yazdır(</span>)',
    r'<span id="sm-btn-print" class="hidden sm:inline">Yazdır\2',
    html, count=1
)
html = re.sub(
    r'(<span[^>]*hidden sm:inline[^>]*>)PDF İndir(</span>)',
    r'<span id="sm-btn-pdf" class="hidden sm:inline">PDF İndir\2',
    html, count=1
)
html = re.sub(
    r'(<span[^>]*hidden sm:inline[^>]*>)Panele Dön(</span>)',
    r'<span id="sm-btn-back" class="hidden sm:inline">Panele Dön\2',
    html, count=1
)

# Find title and main section elements
html = re.sub(
    r'(<h1[^>]*font-bold[^>]*>)([^<]*(?:Özet|Klinik|Rapor)[^<]*)(</h1>)',
    lambda m: f'{m.group(1)}<span id="sm-page-title">{m.group(2)}</span>{m.group(3)}',
    html, count=1
)

# Add i18n init script
sm_i18n_init = """
// ── i18n: inherit language from localStorage ─────────────────────────────────
const SM_DICT = {
  tr: {
    btnPrint:'Yazdır', btnPdf:'PDF İndir', btnBack:'Panele Dön',
    loading:'Yükleniyor...',
    triageLabel:{RED:'🔴 KIRMIZI', YELLOW:'🟡 SARI', GREEN:'🟢 YEŞİL'},
    triageLabelFull:{RED:'ACİL MÜDAHALE', YELLOW:'ACİL / BEKLEYEBİLİR', GREEN:'RUTIN KUYRUK'},
    noFlags:'Acil bulgu yok',
  },
  en: {
    btnPrint:'Print', btnPdf:'Download PDF', btnBack:'Back to Panel',
    loading:'Loading...',
    triageLabel:{RED:'🔴 RED', YELLOW:'🟡 YELLOW', GREEN:'🟢 GREEN'},
    triageLabelFull:{RED:'EMERGENCY', YELLOW:'URGENT / CAN WAIT', GREEN:'ROUTINE QUEUE'},
    noFlags:'No urgent flags',
  },
  ar: {
    btnPrint:'طباعة', btnPdf:'تنزيل PDF', btnBack:'العودة للوحة',
    loading:'جارٍ التحميل...',
    triageLabel:{RED:'🔴 أحمر', YELLOW:'🟡 أصفر', GREEN:'🟢 أخضر'},
    triageLabelFull:{RED:'طوارئ', YELLOW:'عاجل / انتظار', GREEN:'طابور روتيني'},
    noFlags:'لا توجد إشارات إلحاح',
  },
};
const smLang = localStorage.getItem('ui_lang') || 'tr';
function smT(key) { return (SM_DICT[smLang] || SM_DICT.tr)[key] || key; }
function applySMLang() {
  document.documentElement.lang = smLang;
  document.documentElement.dir = smLang === 'ar' ? 'rtl' : 'ltr';
  const m = {
    'sm-btn-print': smT('btnPrint'),
    'sm-btn-pdf': smT('btnPdf'),
    'sm-btn-back': smT('btnBack'),
  };
  Object.entries(m).forEach(([id, val]) => {
    const el = document.getElementById(id); if (el) el.textContent = val;
  });
}
(function(){ applySMLang(); })();
"""

# Insert before last </script>
last_script_end = html.rfind('</script>')
if last_script_end >= 0:
    html = html[:last_script_end] + sm_i18n_init + '\n' + html[last_script_end:]
    print("  ✓ Added SM_DICT + applySMLang()")

# Fix triage labels in renderSummary/renderResult
# Look for hardcoded RED/YELLOW/GREEN label strings
for old, key in [
    ("'🔴 KIRMIZI'", "smT('triageLabel').RED"),
    ("'🟡 SARI'", "smT('triageLabel').YELLOW"),
    ("'🟢 YEŞİL'", "smT('triageLabel').GREEN"),
    ('"🔴 KIRMIZI"', "(SM_DICT[smLang]||SM_DICT.tr).triageLabel.RED"),
    ('"🟡 SARI"', "(SM_DICT[smLang]||SM_DICT.tr).triageLabel.YELLOW"),
    ('"🟢 YEŞİL"', "(SM_DICT[smLang]||SM_DICT.tr).triageLabel.GREEN"),
]:
    if old in html:
        html = html.replace(old, key)
        print(f"  ✓ Replaced: {old}")

with open(os.path.join(FRONTEND, "summary.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("  Saved summary.html")

# ─── login.html quick fix ────────────────────────────────────────────────────
print("\n=== login.html ===")
with open(os.path.join(FRONTEND, "login.html"), encoding="utf-8") as f:
    lhtml = f.read()

# Check if i18n already exists
if 'login_lang' in lhtml or 'LL_DICT' in lhtml:
    print("  Already has i18n, skipping")
else:
    # Add ID to logout/switch account button
    lhtml = lhtml.replace(
        'Çıkış Yap / Farklı Hesap',
        '<span id="lg-btn-logout">Çıkış Yap / Farklı Hesap</span>'
    )
    lhtml = lhtml.replace(
        '>Çıkış Yap<',
        '><span id="lg-btn-logout">Çıkış Yap</span><'
    )
    # Add minimal init
    lg_i18n = """
// i18n: apply stored language
(function(){
  const l = localStorage.getItem('ui_lang') || 'tr';
  document.documentElement.lang = l;
  document.documentElement.dir = l === 'ar' ? 'rtl' : 'ltr';
  const logoutEl = document.getElementById('lg-btn-logout');
  if (logoutEl) {
    const labels = {tr:'Çıkış Yap / Farklı Hesap', en:'Logout / Switch Account', ar:'تسجيل الخروج / تغيير الحساب'};
    logoutEl.textContent = labels[l] || labels.tr;
  }
})();
"""
    last_end = lhtml.rfind('</script>')
    if last_end >= 0:
        lhtml = lhtml[:last_end] + lg_i18n + '\n' + lhtml[last_end:]
    with open(os.path.join(FRONTEND, "login.html"), "w", encoding="utf-8") as f:
        f.write(lhtml)
    print("  ✓ Added minimal login.html i18n")

print("\n✅ All fixes applied!")


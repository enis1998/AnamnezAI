#!/usr/bin/env python3
"""Comprehensive i18n fix for admin.html + doctor.html remaining issues."""
import re, os

FRONTEND = r"C:\Users\pc\Desktop\Health\mediscreen\frontend"

# ─── ADMIN.HTML ──────────────────────────────────────────────────────────────
with open(os.path.join(FRONTEND, "admin.html"), encoding="utf-8") as f:
    html = f.read()

# 1. Add IDs to static HTML elements
replacements = [
    # Header title
    ('<h1 class="font-head font-bold text-[16px]">Admin Paneli</h1>',
     '<h1 id="txt-admin-title" class="font-head font-bold text-[16px]">Admin Paneli</h1>'),

    # Stat card labels
    ('<p class="text-[11px] text-onsv">Toplam Kullanıcı</p>',
     '<p class="text-[11px] text-onsv" id="txt-stat-total-users">Toplam Kullanıcı</p>'),
    ('<p class="text-[11px] text-onsv">Doktor</p>',
     '<p class="text-[11px] text-onsv" id="txt-stat-doctors">Doktor</p>'),
    ('<p class="text-[11px] text-onsv">Oturum (RAM)</p>',
     '<p class="text-[11px] text-onsv" id="txt-stat-sessions">Oturum (RAM)</p>'),
    ('<p class="text-[11px] text-onsv">Görüldü İşaretli</p>',
     '<p class="text-[11px] text-onsv" id="txt-stat-seen">Görüldü İşaretli</p>'),

    # Section headers
    ('<h2 class="font-head font-bold text-pri text-[14px] mb-4">Kuyruk Durumu</h2>',
     '<h2 id="txt-section-queue" class="font-head font-bold text-pri text-[14px] mb-4">Kuyruk Durumu</h2>'),
    ('<span class="text-[13px] text-ons">Aktif kuyruk</span>',
     '<span id="txt-queue-active" class="text-[13px] text-ons">Aktif kuyruk</span>'),
    ('<span class="text-[13px] text-ons">DB\'deki toplam oturum</span>',
     '<span id="txt-queue-db" class="text-[13px] text-ons">DB\'deki toplam oturum</span>'),
    ('<span class="text-[13px] text-ons">AI modeli</span>',
     '<span id="txt-queue-model" class="text-[13px] text-ons">AI modeli</span>'),

    ('<h2 class="font-head font-bold text-pri text-[14px] mb-4">Hızlı İşlemler</h2>',
     '<h2 id="txt-section-actions" class="font-head font-bold text-pri text-[14px] mb-4">Hızlı İşlemler</h2>'),

    # Action buttons
    ('<span class="material-symbols-outlined msym text-[16px]">download</span>Analytics CSV İndir',
     '<span class="material-symbols-outlined msym text-[16px]">download</span><span id="txt-btn-csv">Analytics CSV İndir</span>'),
    ('<span class="material-symbols-outlined msym text-[16px]">cleaning_services</span>Eski Oturumları Temizle',
     '<span class="material-symbols-outlined msym text-[16px]">cleaning_services</span><span id="txt-btn-cleanup">Eski Oturumları Temizle</span>'),
    ('<span class="material-symbols-outlined msym text-[16px]">refresh</span>İstatistikleri Yenile',
     '<span class="material-symbols-outlined msym text-[16px]">refresh</span><span id="txt-btn-refresh-stats">İstatistikleri Yenile</span>'),

    ('<h2 class="font-head font-bold text-pri text-[14px] mb-4">Rol Dağılımı</h2>',
     '<h2 id="txt-section-roles" class="font-head font-bold text-pri text-[14px] mb-4">Rol Dağılımı</h2>'),

    # User list title
    ('<h2 class="font-head font-bold text-pri text-[16px]">Kullanıcı Listesi</h2>',
     '<h2 id="txt-user-list-title" class="font-head font-bold text-pri text-[16px]">Kullanıcı Listesi</h2>'),

    # Audit refresh button
    ('<span class="material-symbols-outlined msym text-[14px]">refresh</span>Yenile\n        </button>',
     '<span class="material-symbols-outlined msym text-[14px]">refresh</span><span id="txt-audit-refresh">Yenile</span>\n        </button>'),

    # Kiosk section
    ('<h2 class="font-head font-bold text-pri text-[15px] mb-5">Kiosk Durumu</h2>',
     '<h2 id="txt-kiosk-status-title" class="font-head font-bold text-pri text-[15px] mb-5">Kiosk Durumu</h2>'),
    ('<span class="material-symbols-outlined msym text-[16px]">lock</span>Kilitle',
     '<span class="material-symbols-outlined msym text-[16px]">lock</span><span id="txt-btn-lock">Kilitle</span>'),
    ('<span class="material-symbols-outlined msym text-[16px]">lock_open</span>Kilidi Aç',
     '<span class="material-symbols-outlined msym text-[16px]">lock_open</span><span id="txt-btn-unlock">Kilidi Aç</span>'),
    ('<h2 class="font-head font-bold text-pri text-[15px] mb-4">Kiosk Hakkında</h2>',
     '<h2 id="txt-kiosk-about-title" class="font-head font-bold text-pri text-[15px] mb-4">Kiosk Hakkında</h2>'),
    ('<p class="text-ons">Kiosk kilitleme, hastaların yeni mülakat başlatmasını engeller. Acil durumlarda veya sistem bakımında kullanın.</p>',
     '<p id="txt-kiosk-info1" class="text-ons">Kiosk kilitleme, hastaların yeni mülakat başlatmasını engeller. Acil durumlarda veya sistem bakımında kullanın.</p>'),
    ('<p class="text-ons">Kioskta tamamlanan her oturum için QR kod oluşturulur. Hasta bu QR ile kendi raporuna erişebilir.</p>',
     '<p id="txt-kiosk-info2" class="text-ons">Kioskta tamamlanan her oturum için QR kod oluşturulur. Hasta bu QR ile kendi raporuna erişebilir.</p>'),
    ('<span class="material-symbols-outlined msym text-[14px]">open_in_new</span>Kiosk Sayfası',
     '<span class="material-symbols-outlined msym text-[14px]">open_in_new</span><span id="txt-kiosk-page">Kiosk Sayfası</span>'),

    # RAG section
    ('<h2 class="font-head font-bold text-pri text-[14px]">RAG Veritabanı Durumu</h2>',
     '<h2 id="txt-rag-db-title" class="font-head font-bold text-pri text-[14px]">RAG Veritabanı Durumu</h2>'),
    ('<h2 class="font-head font-bold text-pri text-[14px]">Metin Ekle</h2>',
     '<h2 id="txt-rag-text-title" class="font-head font-bold text-pri text-[14px]">Metin Ekle</h2>'),
    ('<label class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Kaynak Adı</label>',
     '<label id="txt-rag-source-lbl" class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Kaynak Adı</label>'),
    ('<label class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Kategori</label>',
     '<label id="txt-rag-cat-lbl" class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Kategori</label>'),
    ('<label class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Metin (min. 20 karakter)</label>',
     '<label id="txt-rag-text-lbl" class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Metin (min. 20 karakter)</label>'),
    ('<span class="material-symbols-outlined msym text-[15px]">add_circle</span>RAG\'a Ekle',
     '<span class="material-symbols-outlined msym text-[15px]">add_circle</span><span id="txt-rag-add-btn">RAG\'a Ekle</span>'),
    ('<h2 class="font-head font-bold text-pri text-[14px]">PDF Yükle</h2>',
     '<h2 id="txt-rag-pdf-title" class="font-head font-bold text-pri text-[14px]">PDF Yükle</h2>'),
    ('<span class="text-[12px] font-semibold text-onsv">PDF seç veya sürükle</span>',
     '<span id="txt-rag-pdf-drop" class="text-[12px] font-semibold text-onsv">PDF seç veya sürükle</span>'),
    ('<h2 class="font-head font-bold text-pri text-[14px]">Yerleşik Bilgi Tabanı</h2>',
     '<h2 id="txt-rag-builtin-title" class="font-head font-bold text-pri text-[14px]">Yerleşik Bilgi Tabanı</h2>'),
    ('<p class="text-[12px] text-onsv mb-4">MTS protokolleri, ICD-10 TR, Türkiye acil servis istatistikleri ve genişletilmiş klinik algoritmalar dahil onlarca tıbbi bilgi chunk\'ı yeniden yükler.</p>',
     '<p id="txt-rag-builtin-desc" class="text-[12px] text-onsv mb-4">MTS protokolleri, ICD-10 TR, Türkiye acil servis istatistikleri ve genişletilmiş klinik algoritmalar dahil onlarca tıbbi bilgi chunk\'ı yeniden yükler.</p>'),
    ('<span class="material-symbols-outlined msym text-[15px]">sync</span>Yerleşik Bilgiyi Yenile',
     '<span class="material-symbols-outlined msym text-[15px]">sync</span><span id="txt-rag-builtin-btn">Yerleşik Bilgiyi Yenile</span>'),

    # Compare section
    ('<h2 class="font-head font-bold text-pri text-[15px]">Gemma 4 vs Lite Model Karşılaştırması</h2>',
     '<h2 id="txt-cmp-title" class="font-head font-bold text-pri text-[15px]">Gemma 4 vs Lite Model Karşılaştırması</h2>'),
    ('<p class="text-[12px] text-onsv">Aynı klinik soru için iki modelin yanıtlarını yan yana görün</p>',
     '<p id="txt-cmp-sub" class="text-[12px] text-onsv">Aynı klinik soru için iki modelin yanıtlarını yan yana görün</p>'),
    ('<label class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Sistem Rolü (opsiyonel)</label>',
     '<label id="txt-cmp-sys-lbl" class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Sistem Rolü (opsiyonel)</label>'),
    ('<span class="material-symbols-outlined msym text-[15px]">play_arrow</span>Karşılaştır',
     '<span class="material-symbols-outlined msym text-[15px]">play_arrow</span><span id="txt-cmp-run-btn">Karşılaştır</span>'),
    ('<label class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Klinik Soru / Prompt</label>',
     '<label id="txt-cmp-prompt-lbl" class="block text-[10px] font-bold text-onsv uppercase tracking-wider mb-1">Klinik Soru / Prompt</label>'),
]

for old, new in replacements:
    if old in html:
        html = html.replace(old, new, 1)
        print(f"  ✓ Replaced: {old[:60].strip()}")
    else:
        print(f"  ✗ NOT FOUND: {old[:60].strip()}")

# 2. Expand ADL dictionary
old_adl_tr = """  tr: {
    adminTitle:'Admin Paneli', doctorPanel:'Doktor Paneli', logout:'Çıkış',
    tabStats:'Sistem', tabUsers:'Kullanıcılar', tabAudit:'Audit Log',
    tabKiosk:'Kiosk', tabRag:'RAG', tabCompare:'Model Karşılaştır',
    csvBtn:'Analytics CSV İndir', cleanupBtn:'Eski Oturumları Temizle',
    refreshBtn:'İstatistikleri Yenile',
    searchPlaceholder:'İsim veya e-posta ara...', allRoles:'Tüm Roller',
    userList:'Kullanıcı Listesi',
  },"""
new_adl_tr = """  tr: {
    adminTitle:'Admin Paneli', doctorPanel:'Doktor Paneli', logout:'Çıkış',
    tabStats:'Sistem', tabUsers:'Kullanıcılar', tabAudit:'Audit Log',
    tabKiosk:'Kiosk', tabRag:'RAG', tabCompare:'Model Karşılaştır',
    csvBtn:'Analytics CSV İndir', cleanupBtn:'Eski Oturumları Temizle',
    refreshBtn:'İstatistikleri Yenile',
    searchPlaceholder:'İsim veya e-posta ara...', allRoles:'Tüm Roller',
    userList:'Kullanıcı Listesi',
    // Stats
    statTotalUsers:'Toplam Kullanıcı', statDoctors:'Doktor',
    statSessions:'Oturum (RAM)', statSeen:'Görüldü İşaretli',
    sectionQueue:'Kuyruk Durumu', sectionActions:'Hızlı İşlemler', sectionRoles:'Rol Dağılımı',
    queueActive:'Aktif kuyruk', queueDb:'DB\'deki toplam oturum', queueModel:'AI modeli',
    // Kiosk
    kioskStatusTitle:'Kiosk Durumu', kioskAboutTitle:'Kiosk Hakkında',
    btnLock:'Kilitle', btnUnlock:'Kilidi Aç', kioskPage:'Kiosk Sayfası',
    kioskInfo1:'Kiosk kilitleme, hastaların yeni mülakat başlatmasını engeller. Acil durumlarda veya sistem bakımında kullanın.',
    kioskInfo2:'Kioskta tamamlanan her oturum için QR kod oluşturulur. Hasta bu QR ile kendi raporuna erişebilir.',
    kioskLocked:'🔒 Kiosk Kilitli', kioskUnlocked:'✅ Kiosk Açık',
    kioskLockedSub:'Hasta girişi devre dışı', kioskUnlockedSub:'Hasta girişi aktif',
    kioskChecking:'Kontrol ediliyor...', kioskConnErr:'Bağlantı hatası',
    // RAG
    ragDbTitle:'RAG Veritabanı Durumu', ragTextTitle:'Metin Ekle',
    ragSourceLbl:'Kaynak Adı', ragCatLbl:'Kategori', ragTextLbl:'Metin (min. 20 karakter)',
    ragAddBtn:'RAG\'a Ekle', ragPdfTitle:'PDF Yükle', ragPdfDrop:'PDF seç veya sürükle',
    ragBuiltinTitle:'Yerleşik Bilgi Tabanı', ragBuiltinBtn:'Yerleşik Bilgiyi Yenile',
    ragBuiltinDesc:'MTS protokolleri, ICD-10 TR, Türkiye acil servis istatistikleri ve genişletilmiş klinik algoritmalar dahil onlarca tıbbi bilgi chunk\'ı yeniden yükler.',
    // Compare
    cmpTitle:'Gemma 4 vs Lite Model Karşılaştırması',
    cmpSub:'Aynı klinik soru için iki modelin yanıtlarını yan yana görün',
    cmpSysLbl:'Sistem Rolü (opsiyonel)', cmpPromptLbl:'Klinik Soru / Prompt',
    cmpRunBtn:'Karşılaştır',
    // Audit
    auditRefresh:'Yenile',
    // Table headers
    tbName:'Ad Soyad', tbEmail:'E-posta', tbRole:'Rol',
    tbSpecialty:'Uzmanlık', tbStatus:'Durum', tbActions:'İşlemler',
    tbTime:'Zaman', tbAction:'İşlem', tbUserRole:'Kullanıcı Rol', tbIP:'IP', tbDetail:'Detay',
    // Role labels
    roleDoctor:'Doktor', rolePatient:'Hasta', roleAdmin:'Admin', rolePersonnel:'Personel',
    roleActive:'✓ Aktif', roleInactive:'Pasif',
    btnEnable:'Aktif Et', btnDisable:'Devre Dışı',
    noUsers:'Kullanıcı bulunamadı.', noLogs:'Henüz log kaydı yok.',
    errPermission:'Yetki hatası.', errConnection:'Bağlantı hatası.',
    errStats:'İstatistikler yüklenemedi', ragActive:'✅ RAG Aktif',
    ragInactive:'⚠ RAG devre dışı veya başlatılmamış. Aşağıdan yerleşik bilgiyi yükleyin.',
    noSources:'Henüz kaynak yok.', sourceUnit:'kaynak',
    ragTextShort:'⚠ Metin çok kısa (min 20 karakter)',
    uploading:'⏳ Yükleniyor...',
    ragBuiltinLoading:'⏳ Yerleşik bilgi yükleniyor...',
    cmpRunning:'⏳ İki model paralel olarak sorgulanıyor...',
    cmpDoneFn:(s)=>`✅ Karşılaştırma tamamlandı (${s}s)`,
    cleanupConfirm:'Görüldü işaretlenen tüm eski oturumlar RAM\'den temizlenecek. Emin misiniz?',
    roleUpdated:'Rol güncellendi ✓', roleUpdateFail:'Rol değiştirilemedi.',
    userEnabled:'Kullanıcı aktif edildi ✓', userDisabled:'Kullanıcı devre dışı ✓',
    processingBg:'arka planda işleniyor',
    adminOnly:'⛔ Bu sayfa yalnızca admin için.',
    csvDownloaded:'CSV indirildi ✓', csvFailed:'CSV indirilemedi.',
    toastCleanedFn:(n)=>`✅ ${n} oturum temizlendi.`,
    toastCleanupFail:'Temizleme başarısız.',
  },"""

if old_adl_tr in html:
    html = html.replace(old_adl_tr, new_adl_tr, 1)
    print("  ✓ ADL TR expanded")
else:
    print("  ✗ ADL TR not found exactly - trying partial match")
    # Try with normalized whitespace
    idx = html.find("tr: {\n    adminTitle:'Admin Paneli'")
    if idx >= 0:
        print(f"    Found TR block at {idx}")

old_adl_en = """  en: {
    adminTitle:'Admin Panel', doctorPanel:'Doctor Panel', logout:'Logout',
    tabStats:'System', tabUsers:'Users', tabAudit:'Audit Log',
    tabKiosk:'Kiosk', tabRag:'RAG', tabCompare:'Model Compare',
    csvBtn:'Download Analytics CSV', cleanupBtn:'Clean Old Sessions',
    refreshBtn:'Refresh Stats',
    searchPlaceholder:'Search name or email...', allRoles:'All Roles',
    userList:'User List',
  },"""
new_adl_en = """  en: {
    adminTitle:'Admin Panel', doctorPanel:'Doctor Panel', logout:'Logout',
    tabStats:'System', tabUsers:'Users', tabAudit:'Audit Log',
    tabKiosk:'Kiosk', tabRag:'RAG', tabCompare:'Model Compare',
    csvBtn:'Download Analytics CSV', cleanupBtn:'Clean Old Sessions',
    refreshBtn:'Refresh Stats',
    searchPlaceholder:'Search name or email...', allRoles:'All Roles',
    userList:'User List',
    // Stats
    statTotalUsers:'Total Users', statDoctors:'Doctors',
    statSessions:'Sessions (RAM)', statSeen:'Marked Seen',
    sectionQueue:'Queue Status', sectionActions:'Quick Actions', sectionRoles:'Role Distribution',
    queueActive:'Active queue', queueDb:'DB total sessions', queueModel:'AI model',
    // Kiosk
    kioskStatusTitle:'Kiosk Status', kioskAboutTitle:'About Kiosk',
    btnLock:'Lock', btnUnlock:'Unlock', kioskPage:'Kiosk Page',
    kioskInfo1:'Kiosk lock prevents patients from starting new interviews. Use during emergencies or maintenance.',
    kioskInfo2:'Each kiosk session generates a QR code. Patients can access their report via this QR.',
    kioskLocked:'🔒 Kiosk Locked', kioskUnlocked:'✅ Kiosk Open',
    kioskLockedSub:'Patient entry disabled', kioskUnlockedSub:'Patient entry active',
    kioskChecking:'Checking...', kioskConnErr:'Connection error',
    // RAG
    ragDbTitle:'RAG Database Status', ragTextTitle:'Add Text',
    ragSourceLbl:'Source Name', ragCatLbl:'Category', ragTextLbl:'Text (min. 20 chars)',
    ragAddBtn:'Add to RAG', ragPdfTitle:'Upload PDF', ragPdfDrop:'Select or drop PDF',
    ragBuiltinTitle:'Built-in Knowledge Base', ragBuiltinBtn:'Reload Built-in Knowledge',
    ragBuiltinDesc:'Reloads dozens of medical knowledge chunks including MTS protocols, ICD-10, Turkey ER statistics, and extended clinical algorithms.',
    // Compare
    cmpTitle:'Gemma 4 vs Lite Model Comparison',
    cmpSub:'View responses from both models side by side for the same clinical query',
    cmpSysLbl:'System Role (optional)', cmpPromptLbl:'Clinical Question / Prompt',
    cmpRunBtn:'Compare',
    // Audit
    auditRefresh:'Refresh',
    // Table headers
    tbName:'Full Name', tbEmail:'Email', tbRole:'Role',
    tbSpecialty:'Specialty', tbStatus:'Status', tbActions:'Actions',
    tbTime:'Time', tbAction:'Action', tbUserRole:'User Role', tbIP:'IP', tbDetail:'Detail',
    // Role labels
    roleDoctor:'Doctor', rolePatient:'Patient', roleAdmin:'Admin', rolePersonnel:'Personnel',
    roleActive:'✓ Active', roleInactive:'Inactive',
    btnEnable:'Activate', btnDisable:'Disable',
    noUsers:'No users found.', noLogs:'No log entries yet.',
    errPermission:'Permission error.', errConnection:'Connection error.',
    errStats:'Could not load stats', ragActive:'✅ RAG Active',
    ragInactive:'⚠ RAG disabled or not initialized. Load built-in knowledge below.',
    noSources:'No sources yet.', sourceUnit:'sources',
    ragTextShort:'⚠ Text too short (min 20 chars)',
    uploading:'⏳ Uploading...',
    ragBuiltinLoading:'⏳ Loading built-in knowledge...',
    cmpRunning:'⏳ Querying both models in parallel...',
    cmpDoneFn:(s)=>`✅ Comparison complete (${s}s)`,
    cleanupConfirm:'All seen-marked old sessions will be cleared from RAM. Are you sure?',
    roleUpdated:'Role updated ✓', roleUpdateFail:'Could not change role.',
    userEnabled:'User activated ✓', userDisabled:'User disabled ✓',
    processingBg:'processing in background',
    adminOnly:'⛔ This page is for admins only.',
    csvDownloaded:'CSV downloaded ✓', csvFailed:'CSV download failed.',
    toastCleanedFn:(n)=>`✅ ${n} session(s) cleaned.`,
    toastCleanupFail:'Cleanup failed.',
  },"""

if old_adl_en in html:
    html = html.replace(old_adl_en, new_adl_en, 1)
    print("  ✓ ADL EN expanded")
else:
    print("  ✗ ADL EN not found exactly")

old_adl_ar = """  ar: {
    adminTitle:'لوحة المشرف', doctorPanel:'لوحة الطبيب', logout:'تسجيل الخروج',
    tabStats:'النظام', tabUsers:'المستخدمون', tabAudit:'سجل التدقيق',
    tabKiosk:'الكشك', tabRag:'RAG', tabCompare:'مقارنة النموذج',
    csvBtn:'تنزيل CSV التحليلات', cleanupBtn:'تنظيف الجلسات القديمة',
    refreshBtn:'تحديث الإحصائيات',
    searchPlaceholder:'ابحث عن الاسم أو البريد...', allRoles:'جميع الأدوار',
    userList:'قائمة المستخدمين',
  },"""
new_adl_ar = """  ar: {
    adminTitle:'لوحة المشرف', doctorPanel:'لوحة الطبيب', logout:'تسجيل الخروج',
    tabStats:'النظام', tabUsers:'المستخدمون', tabAudit:'سجل التدقيق',
    tabKiosk:'الكشك', tabRag:'RAG', tabCompare:'مقارنة النموذج',
    csvBtn:'تنزيل CSV التحليلات', cleanupBtn:'تنظيف الجلسات القديمة',
    refreshBtn:'تحديث الإحصائيات',
    searchPlaceholder:'ابحث عن الاسم أو البريد...', allRoles:'جميع الأدوار',
    userList:'قائمة المستخدمين',
    // Stats
    statTotalUsers:'إجمالي المستخدمين', statDoctors:'الأطباء',
    statSessions:'الجلسات (RAM)', statSeen:'تم التعليم',
    sectionQueue:'حالة الطابور', sectionActions:'إجراءات سريعة', sectionRoles:'توزيع الأدوار',
    queueActive:'الطابور النشط', queueDb:'إجمالي جلسات DB', queueModel:'نموذج الذكاء',
    // Kiosk
    kioskStatusTitle:'حالة الكشك', kioskAboutTitle:'عن الكشك',
    btnLock:'قفل', btnUnlock:'فتح', kioskPage:'صفحة الكشك',
    kioskInfo1:'يمنع قفل الكشك المرضى من بدء مقابلات جديدة. استخدمه في حالات الطوارئ أو الصيانة.',
    kioskInfo2:'يتم إنشاء رمز QR لكل جلسة كشك. يمكن للمرضى الوصول إلى تقاريرهم عبر هذا الرمز.',
    kioskLocked:'🔒 الكشك مقفل', kioskUnlocked:'✅ الكشك مفتوح',
    kioskLockedSub:'دخول المرضى معطّل', kioskUnlockedSub:'دخول المرضى نشط',
    kioskChecking:'جارٍ الفحص...', kioskConnErr:'خطأ في الاتصال',
    // RAG
    ragDbTitle:'حالة قاعدة بيانات RAG', ragTextTitle:'إضافة نص',
    ragSourceLbl:'اسم المصدر', ragCatLbl:'الفئة', ragTextLbl:'النص (20 حرفاً كحد أدنى)',
    ragAddBtn:'أضف إلى RAG', ragPdfTitle:'رفع PDF', ragPdfDrop:'اختر أو اسحب PDF',
    ragBuiltinTitle:'قاعدة المعرفة المدمجة', ragBuiltinBtn:'إعادة تحميل المعرفة المدمجة',
    ragBuiltinDesc:'يعيد تحميل عشرات أجزاء المعرفة الطبية بما في ذلك بروتوكولات MTS وICD-10.',
    // Compare
    cmpTitle:'مقارنة Gemma 4 مع النموذج الخفيف',
    cmpSub:'شاهد استجابات كلا النموذجين جنباً إلى جنب لنفس الاستعلام',
    cmpSysLbl:'دور النظام (اختياري)', cmpPromptLbl:'السؤال السريري / الطلب',
    cmpRunBtn:'مقارنة',
    // Audit
    auditRefresh:'تحديث',
    // Table headers
    tbName:'الاسم الكامل', tbEmail:'البريد الإلكتروني', tbRole:'الدور',
    tbSpecialty:'التخصص', tbStatus:'الحالة', tbActions:'الإجراءات',
    tbTime:'الوقت', tbAction:'الإجراء', tbUserRole:'دور المستخدم', tbIP:'IP', tbDetail:'التفاصيل',
    // Role labels
    roleDoctor:'طبيب', rolePatient:'مريض', roleAdmin:'مشرف', rolePersonnel:'موظف',
    roleActive:'✓ نشط', roleInactive:'غير نشط',
    btnEnable:'تفعيل', btnDisable:'تعطيل',
    noUsers:'لم يُعثر على مستخدمين.', noLogs:'لا توجد سجلات بعد.',
    errPermission:'خطأ في الصلاحيات.', errConnection:'خطأ في الاتصال.',
    errStats:'تعذّر تحميل الإحصائيات', ragActive:'✅ RAG نشط',
    ragInactive:'⚠ RAG معطّل أو غير مُهيّأ. حمّل المعرفة المدمجة أدناه.',
    noSources:'لا توجد مصادر بعد.', sourceUnit:'مصادر',
    ragTextShort:'⚠ النص قصير جداً (20 حرفاً كحد أدنى)',
    uploading:'⏳ جارٍ الرفع...',
    ragBuiltinLoading:'⏳ جارٍ تحميل المعرفة المدمجة...',
    cmpRunning:'⏳ جارٍ الاستعلام عن كلا النموذجين...',
    cmpDoneFn:(s)=>`✅ اكتملت المقارنة (${s}s)`,
    cleanupConfirm:'ستُحذف جميع الجلسات القديمة المعلّمة من الذاكرة. هل أنت متأكد؟',
    roleUpdated:'تم تحديث الدور ✓', roleUpdateFail:'تعذّر تغيير الدور.',
    userEnabled:'تم تفعيل المستخدم ✓', userDisabled:'تم تعطيل المستخدم ✓',
    processingBg:'تتم المعالجة في الخلفية',
    adminOnly:'⛔ هذه الصفحة للمشرفين فقط.',
    csvDownloaded:'تم تنزيل CSV ✓', csvFailed:'فشل تنزيل CSV.',
    toastCleanedFn:(n)=>`✅ تم تنظيف ${n} جلسة.`,
    toastCleanupFail:'فشل التنظيف.',
  },"""

if old_adl_ar in html:
    html = html.replace(old_adl_ar, new_adl_ar, 1)
    print("  ✓ ADL AR expanded")
else:
    print("  ✗ ADL AR not found exactly")

# 3. Expand setAdminLang() to handle all new IDs
old_setlang = """  const m = {
    'txt-admin-doctor-panel': d.doctorPanel,
    'txt-admin-logout': d.logout,
  };
  Object.entries(m).forEach(([id, val]) => { const el = document.getElementById(id); if (el) el.textContent = val; });"""

new_setlang = """  const m = {
    'txt-admin-title': d.adminTitle,
    'txt-admin-doctor-panel': d.doctorPanel,
    'txt-admin-logout': d.logout,
    'txt-stat-total-users': d.statTotalUsers, 'txt-stat-doctors': d.statDoctors,
    'txt-stat-sessions': d.statSessions, 'txt-stat-seen': d.statSeen,
    'txt-section-queue': d.sectionQueue, 'txt-section-actions': d.sectionActions,
    'txt-section-roles': d.sectionRoles,
    'txt-queue-active': d.queueActive, 'txt-queue-db': d.queueDb, 'txt-queue-model': d.queueModel,
    'txt-btn-csv': d.csvBtn, 'txt-btn-cleanup': d.cleanupBtn, 'txt-btn-refresh-stats': d.refreshBtn,
    'txt-user-list-title': d.userList, 'txt-audit-refresh': d.auditRefresh,
    'txt-kiosk-status-title': d.kioskStatusTitle, 'txt-kiosk-about-title': d.kioskAboutTitle,
    'txt-btn-lock': d.btnLock, 'txt-btn-unlock': d.btnUnlock, 'txt-kiosk-page': d.kioskPage,
    'txt-kiosk-info1': d.kioskInfo1, 'txt-kiosk-info2': d.kioskInfo2,
    'txt-rag-db-title': d.ragDbTitle, 'txt-rag-text-title': d.ragTextTitle,
    'txt-rag-source-lbl': d.ragSourceLbl, 'txt-rag-cat-lbl': d.ragCatLbl,
    'txt-rag-text-lbl': d.ragTextLbl, 'txt-rag-add-btn': d.ragAddBtn,
    'txt-rag-pdf-title': d.ragPdfTitle, 'txt-rag-pdf-drop': d.ragPdfDrop,
    'txt-rag-builtin-title': d.ragBuiltinTitle, 'txt-rag-builtin-btn': d.ragBuiltinBtn,
    'txt-rag-builtin-desc': d.ragBuiltinDesc,
    'txt-cmp-title': d.cmpTitle, 'txt-cmp-sub': d.cmpSub,
    'txt-cmp-sys-lbl': d.cmpSysLbl, 'txt-cmp-prompt-lbl': d.cmpPromptLbl,
    'txt-cmp-run-btn': d.cmpRunBtn,
  };
  Object.entries(m).forEach(([id, val]) => { const el = document.getElementById(id); if (el) el.textContent = val; });"""

if old_setlang in html:
    html = html.replace(old_setlang, new_setlang, 1)
    print("  ✓ setAdminLang() expanded")
else:
    print("  ✗ setAdminLang() not found exactly")

# 4. Make JS functions use adminLang-aware ADL
# Replace ROLE_BADGE hardcoded labels to use ADL function
old_role_badge = """const ROLE_BADGE = {
  doctor:    ['bg-emerald-100 text-emerald-700','Doktor'],
  patient:   ['bg-blue-100 text-blue-700','Hasta'],
  admin:     ['bg-red-100 text-red-700','Admin'],
  personnel: ['bg-amber-100 text-amber-700','Personel'],
};"""
new_role_badge = """function getRoleBadge() {
  const d = ADL[adminLang] || ADL.tr;
  return {
    doctor:    ['bg-emerald-100 text-emerald-700', d.roleDoctor],
    patient:   ['bg-blue-100 text-blue-700', d.rolePatient],
    admin:     ['bg-red-100 text-red-700', d.roleAdmin],
    personnel: ['bg-amber-100 text-amber-700', d.rolePersonnel],
  };
}
const ROLE_BADGE = {
  doctor:    ['bg-emerald-100 text-emerald-700','Doktor'],
  patient:   ['bg-blue-100 text-blue-700','Hasta'],
  admin:     ['bg-red-100 text-red-700','Admin'],
  personnel: ['bg-amber-100 text-amber-700','Personel'],
};"""

if old_role_badge in html:
    html = html.replace(old_role_badge, new_role_badge, 1)
    print("  ✓ ROLE_BADGE -> getRoleBadge()")
else:
    print("  ✗ ROLE_BADGE not found exactly")

# Replace renderUsers to use getRoleBadge()
old_render_users = """function renderUsers(users) {
  const el = document.getElementById('users-table');
  if (!users.length) { el.innerHTML = '<div class="p-8 text-center text-onsv text-[13px]">Kullanıcı bulunamadı.</div>'; return; }
  el.innerHTML = `
  <table class="w-full text-[13px]">
    <thead class="bg-surf text-[11px] font-bold text-onsv uppercase tracking-wider">
      <tr>
        <th class="px-5 py-3 text-left">Ad Soyad</th>
        <th class="px-5 py-3 text-left">E-posta</th>
        <th class="px-5 py-3 text-left">Rol</th>
        <th class="px-5 py-3 text-left">Uzmanlık</th>
        <th class="px-5 py-3 text-left">Durum</th>
        <th class="px-5 py-3 text-left">İşlemler</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-surfc">
      ${users.map(u => {
        const [bc, bl] = ROLE_BADGE[u.role] || ['bg-surfc text-onsv', u.role];
        return `<tr class="hover:bg-surf transition-colors ${!u.is_active?'opacity-50':''}">
          <td class="px-5 py-3 font-semibold text-pri">${u.name}</td>
          <td class="px-5 py-3 text-onsv font-mono text-[12px]">${u.email}</td>
          <td class="px-5 py-3">
            <select onchange="changeRole('${u.user_id}',this.value)"
              class="text-[11px] font-bold px-2 py-1 rounded-lg border border-ouv ${bc} appearance-none cursor-pointer">
              ${['doctor','patient','admin','personnel'].map(r=>
                `<option value="${r}" ${r===u.role?'selected':''}>${ROLE_BADGE[r]?.[1]||r}</option>`
              ).join('')}
            </select>
          </td>
          <td class="px-5 py-3 text-onsv">${u.specialty||'—'}</td>
          <td class="px-5 py-3">
            <span class="badge ${u.is_active?'bg-emerald-100 text-emerald-700':'bg-surfc text-onsv'}">
              ${u.is_active?'✓ Aktif':'Pasif'}
            </span>
          </td>
          <td class="px-5 py-3">
            <button onclick="toggleActive('${u.user_id}',${u.is_active})"
              class="text-[11px] px-2.5 py-1 rounded-lg border ${u.is_active?'border-err text-err hover:bg-err hover:text-white':'border-sec text-sec hover:bg-sec hover:text-white'} transition-all font-semibold">
              ${u.is_active?'Devre Dışı':'Aktif Et'}
            </button>
          </td>
        </tr>`;
      }).join('')}
    </tbody>
  </table>`;
}"""
new_render_users = """function renderUsers(users) {
  const el = document.getElementById('users-table');
  const d = ADL[adminLang] || ADL.tr;
  const rb = getRoleBadge();
  if (!users.length) { el.innerHTML = `<div class="p-8 text-center text-onsv text-[13px]">${d.noUsers}</div>`; return; }
  el.innerHTML = `
  <table class="w-full text-[13px]">
    <thead class="bg-surf text-[11px] font-bold text-onsv uppercase tracking-wider">
      <tr>
        <th class="px-5 py-3 text-left">${d.tbName}</th>
        <th class="px-5 py-3 text-left">${d.tbEmail}</th>
        <th class="px-5 py-3 text-left">${d.tbRole}</th>
        <th class="px-5 py-3 text-left">${d.tbSpecialty}</th>
        <th class="px-5 py-3 text-left">${d.tbStatus}</th>
        <th class="px-5 py-3 text-left">${d.tbActions}</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-surfc">
      ${users.map(u => {
        const [bc, bl] = rb[u.role] || ['bg-surfc text-onsv', u.role];
        return `<tr class="hover:bg-surf transition-colors ${!u.is_active?'opacity-50':''}">
          <td class="px-5 py-3 font-semibold text-pri">${u.name}</td>
          <td class="px-5 py-3 text-onsv font-mono text-[12px]">${u.email}</td>
          <td class="px-5 py-3">
            <select onchange="changeRole('${u.user_id}',this.value)"
              class="text-[11px] font-bold px-2 py-1 rounded-lg border border-ouv ${bc} appearance-none cursor-pointer">
              ${['doctor','patient','admin','personnel'].map(r=>
                `<option value="${r}" ${r===u.role?'selected':''}>${rb[r]?.[1]||r}</option>`
              ).join('')}
            </select>
          </td>
          <td class="px-5 py-3 text-onsv">${u.specialty||'—'}</td>
          <td class="px-5 py-3">
            <span class="badge ${u.is_active?'bg-emerald-100 text-emerald-700':'bg-surfc text-onsv'}">
              ${u.is_active?d.roleActive:d.roleInactive}
            </span>
          </td>
          <td class="px-5 py-3">
            <button onclick="toggleActive('${u.user_id}',${u.is_active})"
              class="text-[11px] px-2.5 py-1 rounded-lg border ${u.is_active?'border-err text-err hover:bg-err hover:text-white':'border-sec text-sec hover:bg-sec hover:text-white'} transition-all font-semibold">
              ${u.is_active?d.btnDisable:d.btnEnable}
            </button>
          </td>
        </tr>`;
      }).join('')}
    </tbody>
  </table>`;
}"""

if old_render_users in html:
    html = html.replace(old_render_users, new_render_users, 1)
    print("  ✓ renderUsers() i18n updated")
else:
    print("  ✗ renderUsers() not found exactly")

# Replace loadAuditLog table headers
old_audit_hdrs = """      <thead class="bg-surf text-[10px] font-bold text-onsv uppercase tracking-wider">
        <tr>
          <th class="px-4 py-2 text-left">Zaman</th>
          <th class="px-4 py-2 text-left">İşlem</th>
          <th class="px-4 py-2 text-left">Kullanıcı Rol</th>
          <th class="px-4 py-2 text-left">IP</th>
          <th class="px-4 py-2 text-left">Detay</th>
        </tr>
      </thead>"""
new_audit_hdrs = """      <thead class="bg-surf text-[10px] font-bold text-onsv uppercase tracking-wider">
        <tr>
          <th class="px-4 py-2 text-left">${_d.tbTime}</th>
          <th class="px-4 py-2 text-left">${_d.tbAction}</th>
          <th class="px-4 py-2 text-left">${_d.tbUserRole}</th>
          <th class="px-4 py-2 text-left">${_d.tbIP}</th>
          <th class="px-4 py-2 text-left">${_d.tbDetail}</th>
        </tr>
      </thead>"""

# Replace loadAuditLog function
old_audit_fn = """async function loadAuditLog() {
  const el = document.getElementById('audit-table');
  el.innerHTML = '<div class="text-center py-8"><span class="material-symbols-outlined msym spin text-sec text-2xl">refresh</span></div>';
  try {
    const r = await fetch(`${API}/api/audit-log?limit=100`, { headers: authHeaders() });
    if (!r.ok) { el.innerHTML = '<div class="p-5 text-err text-[13px]">Yetki hatası veya log bulunamadı.</div>'; return; }
    const d = await r.json();
    const logs = d.logs || [];
    if (!logs.length) { el.innerHTML = '<div class="p-8 text-center text-onsv text-[13px]">Henüz log kaydı yok.</div>'; return; }
    el.innerHTML = `
    <table class="w-full text-[12px]">
      <thead class="bg-surf text-[10px] font-bold text-onsv uppercase tracking-wider">
        <tr>
          <th class="px-4 py-2 text-left">Zaman</th>
          <th class="px-4 py-2 text-left">İşlem</th>
          <th class="px-4 py-2 text-left">Kullanıcı Rol</th>
          <th class="px-4 py-2 text-left">IP</th>
          <th class="px-4 py-2 text-left">Detay</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-surfc">
        ${logs.map(l => `<tr class="hover:bg-surf">
          <td class="px-4 py-2 text-onsv font-mono">${new Date(l.created_at).toLocaleString('tr-TR')}</td>
          <td class="px-4 py-2 font-bold text-pri">${l.action||'—'}</td>
          <td class="px-4 py-2 text-onsv">${l.user_role||'—'}</td>
          <td class="px-4 py-2 font-mono text-onsv">${l.ip_address||'—'}</td>
          <td class="px-4 py-2 text-onsv truncate max-w-xs">${l.details||'—'}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  } catch { el.innerHTML = '<div class="p-5 text-err text-[13px]">Bağlantı hatası.</div>'; }
}"""
new_audit_fn = """async function loadAuditLog() {
  const el = document.getElementById('audit-table');
  const _d = ADL[adminLang] || ADL.tr;
  const locale = adminLang === 'ar' ? 'ar-SA' : adminLang === 'en' ? 'en-US' : 'tr-TR';
  el.innerHTML = '<div class="text-center py-8"><span class="material-symbols-outlined msym spin text-sec text-2xl">refresh</span></div>';
  try {
    const r = await fetch(`${API}/api/audit-log?limit=100`, { headers: authHeaders() });
    if (!r.ok) { el.innerHTML = `<div class="p-5 text-err text-[13px]">${_d.errPermission}</div>`; return; }
    const d = await r.json();
    const logs = d.logs || [];
    if (!logs.length) { el.innerHTML = `<div class="p-8 text-center text-onsv text-[13px]">${_d.noLogs}</div>`; return; }
    el.innerHTML = `
    <table class="w-full text-[12px]">
      <thead class="bg-surf text-[10px] font-bold text-onsv uppercase tracking-wider">
        <tr>
          <th class="px-4 py-2 text-left">${_d.tbTime}</th>
          <th class="px-4 py-2 text-left">${_d.tbAction}</th>
          <th class="px-4 py-2 text-left">${_d.tbUserRole}</th>
          <th class="px-4 py-2 text-left">${_d.tbIP}</th>
          <th class="px-4 py-2 text-left">${_d.tbDetail}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-surfc">
        ${logs.map(l => `<tr class="hover:bg-surf">
          <td class="px-4 py-2 text-onsv font-mono">${new Date(l.created_at).toLocaleString(locale)}</td>
          <td class="px-4 py-2 font-bold text-pri">${l.action||'—'}</td>
          <td class="px-4 py-2 text-onsv">${l.user_role||'—'}</td>
          <td class="px-4 py-2 font-mono text-onsv">${l.ip_address||'—'}</td>
          <td class="px-4 py-2 text-onsv truncate max-w-xs">${l.details||'—'}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  } catch { el.innerHTML = `<div class="p-5 text-err text-[13px]">${_d.errConnection}</div>`; }
}"""

if old_audit_fn in html:
    html = html.replace(old_audit_fn, new_audit_fn, 1)
    print("  ✓ loadAuditLog() i18n updated")
else:
    print("  ✗ loadAuditLog() not found exactly")

# Fix loadKioskStatus to use ADL
old_kiosk_fn = """async function loadKioskStatus() {
  try {
    const r = await fetch(`${API}/api/kiosk/status`);
    const d = await r.json();
    const locked = d.is_locked;
    document.getElementById('kiosk-icon').textContent = locked ? 'lock' : 'tablet';
    document.getElementById('kiosk-icon').style.color = locked ? '#ba1a1a' : '#006a68';
    document.getElementById('kiosk-status-text').textContent = locked ? '🔒 Kiosk Kilitli' : '✅ Kiosk Açık';
    document.getElementById('kiosk-status-sub').textContent = locked ? 'Hasta girişi devre dışı' : 'Hasta girişi aktif';
  } catch { document.getElementById('kiosk-status-text').textContent = 'Bağlantı hatası'; }
}"""
new_kiosk_fn = """async function loadKioskStatus() {
  const _d = ADL[adminLang] || ADL.tr;
  try {
    const r = await fetch(`${API}/api/kiosk/status`);
    const d = await r.json();
    const locked = d.is_locked;
    document.getElementById('kiosk-icon').textContent = locked ? 'lock' : 'tablet';
    document.getElementById('kiosk-icon').style.color = locked ? '#ba1a1a' : '#006a68';
    document.getElementById('kiosk-status-text').textContent = locked ? _d.kioskLocked : _d.kioskUnlocked;
    document.getElementById('kiosk-status-sub').textContent = locked ? _d.kioskLockedSub : _d.kioskUnlockedSub;
  } catch { document.getElementById('kiosk-status-text').textContent = _d.kioskConnErr; }
}"""

if old_kiosk_fn in html:
    html = html.replace(old_kiosk_fn, new_kiosk_fn, 1)
    print("  ✓ loadKioskStatus() i18n updated")
else:
    print("  ✗ loadKioskStatus() not found exactly")

# Fix loadStats role labels
old_role_labels = """    const roleColors = { doctor: '#006a68', patient: '#002f40', admin: '#ba1a1a', personnel: '#e07b26' };
    const roleLabels = { doctor: 'Doktor', patient: 'Hasta', admin: 'Admin', personnel: 'Personel' };"""
new_role_labels = """    const roleColors = { doctor: '#006a68', patient: '#002f40', admin: '#ba1a1a', personnel: '#e07b26' };
    const _ld = ADL[adminLang] || ADL.tr;
    const roleLabels = { doctor: _ld.roleDoctor, patient: _ld.rolePatient, admin: _ld.roleAdmin, personnel: _ld.rolePersonnel };"""

if old_role_labels in html:
    html = html.replace(old_role_labels, new_role_labels, 1)
    print("  ✓ loadStats() role labels i18n updated")
else:
    print("  ✗ loadStats() role labels not found")

# Fix toast messages in changeRole
old_change_role = """    if (!r.ok) { const d = await r.json(); showToast(d.detail || 'Rol değiştirilemedi.', true); loadUsers(); return; }
    showToast('Rol güncellendi ✓');"""
new_change_role = """    const _d2 = ADL[adminLang] || ADL.tr;
    if (!r.ok) { const d = await r.json(); showToast(d.detail || _d2.roleUpdateFail, true); loadUsers(); return; }
    showToast(_d2.roleUpdated);"""

if old_change_role in html:
    html = html.replace(old_change_role, new_change_role, 1)
    print("  ✓ changeRole() toast i18n updated")
else:
    print("  ✗ changeRole() toast not found")

# Fix toggleActive messages
old_toggle = """    if (!r.ok) { showToast('İşlem başarısız.', true); return; }
    showToast(newActive ? 'Kullanıcı aktif edildi ✓' : 'Kullanıcı devre dışı ✓');"""
new_toggle = """    const _d3 = ADL[adminLang] || ADL.tr;
    if (!r.ok) { showToast(_d3.errPermission, true); return; }
    showToast(newActive ? _d3.userEnabled : _d3.userDisabled);"""

if old_toggle in html:
    html = html.replace(old_toggle, new_toggle, 1)
    print("  ✓ toggleActive() toast i18n updated")
else:
    print("  ✗ toggleActive() toast not found")

# Fix clearOldSessions
old_cleanup = """  if (!confirm('Görüldü işaretlenen tüm eski oturumlar RAM\'den temizlenecek. Emin misiniz?')) return;
  try {
    const r = await fetch(`${API}/api/admin/sessions/cleanup`, { method: 'POST', headers: authHeaders() });
    if (!r.ok) { showToast('Temizleme başarısız: ' + r.status, true); return; }
    const d = await r.json();
    showToast(`✅ ${d.cleaned} oturum temizlendi.`);"""
new_cleanup = """  const _d4 = ADL[adminLang] || ADL.tr;
  if (!confirm(_d4.cleanupConfirm)) return;
  try {
    const r = await fetch(`${API}/api/admin/sessions/cleanup`, { method: 'POST', headers: authHeaders() });
    if (!r.ok) { showToast(_d4.toastCleanupFail + ' ' + r.status, true); return; }
    const d = await r.json();
    showToast(_d4.toastCleanedFn(d.cleaned));"""

if old_cleanup in html:
    html = html.replace(old_cleanup, new_cleanup, 1)
    print("  ✓ clearOldSessions() i18n updated")
else:
    print("  ✗ clearOldSessions() not found")

# Fix auth check admin-only message
old_admin_check = """    if (d.user.role !== 'admin') {
      showToast('⛔ Bu sayfa yalnızca admin için.', true);"""
new_admin_check = """    if (d.user.role !== 'admin') {
      showToast((ADL[adminLang]||ADL.tr).adminOnly, true);"""

if old_admin_check in html:
    html = html.replace(old_admin_check, new_admin_check, 1)
    print("  ✓ checkAuth() admin-only i18n updated")
else:
    print("  ✗ checkAuth() not found")

# Fix loadRagStatus
old_rag_status = """    const sources = d.sources || {};
      const sourceHtml = Object.entries(sources).map(([src, cnt]) =>
        `<div class="flex justify-between items-center py-1.5 border-b border-surfc text-[12px]">
          <span class="text-ons font-medium truncate flex-1">${src.replace(/_/g,' ')}</span>
          <span class="font-bold text-sec ml-2">${cnt} chunk</span>
        </div>`
      ).join('') || '<p class="text-ouv text-[12px]">Henüz kaynak yok.</p>';
      el.innerHTML = `
        <div class="flex gap-2 mb-3 flex-wrap">
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700">✅ RAG Aktif</span>
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-secc text-sec">${d.total_chunks} chunk</span>
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-surfc text-onsv">${Object.keys(sources).length} kaynak</span>
        </div>
        <div class="rounded-xl border border-surfc overflow-hidden">${sourceHtml}</div>`;
    } else {
      el.innerHTML = `<div class="p-4 rounded-xl bg-amber-50 text-amber-700 text-[13px]">⚠ RAG devre dışı veya başlatılmamış. Aşağıdan yerleşik bilgiyi yükleyin.</div>`;"""
new_rag_status = """    const sources = d.sources || {};
      const _rd = ADL[adminLang] || ADL.tr;
      const sourceHtml = Object.entries(sources).map(([src, cnt]) =>
        `<div class="flex justify-between items-center py-1.5 border-b border-surfc text-[12px]">
          <span class="text-ons font-medium truncate flex-1">${src.replace(/_/g,' ')}</span>
          <span class="font-bold text-sec ml-2">${cnt} chunk</span>
        </div>`
      ).join('') || `<p class="text-ouv text-[12px]">${_rd.noSources}</p>`;
      el.innerHTML = `
        <div class="flex gap-2 mb-3 flex-wrap">
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700">${_rd.ragActive}</span>
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-secc text-sec">${d.total_chunks} chunk</span>
          <span class="px-3 py-1 rounded-full text-[11px] font-bold bg-surfc text-onsv">${Object.keys(sources).length} ${_rd.sourceUnit}</span>
        </div>
        <div class="rounded-xl border border-surfc overflow-hidden">${sourceHtml}</div>`;
    } else {
      el.innerHTML = `<div class="p-4 rounded-xl bg-amber-50 text-amber-700 text-[13px]">${(ADL[adminLang]||ADL.tr).ragInactive}</div>`;"""

if old_rag_status in html:
    html = html.replace(old_rag_status, new_rag_status, 1)
    print("  ✓ loadRagStatus() i18n updated")
else:
    print("  ✗ loadRagStatus() not found")

# Save admin.html
with open(os.path.join(FRONTEND, "admin.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("\nAdmin.html saved.")

# ─── DOCTOR.HTML — fix remaining "Kiosk Yönetim" nav label ──────────────────
with open(os.path.join(FRONTEND, "doctor.html"), encoding="utf-8") as f:
    doc = f.read()

# Check if Kiosk nav section label has a translatable ID
kiosk_mgmt_idx = doc.find('KIOSK MANAGEMENT')
if kiosk_mgmt_idx < 0:
    kiosk_mgmt_idx = doc.find('Kiosk Yönetim')
    if kiosk_mgmt_idx < 0:
        kiosk_mgmt_idx = doc.find('navKioskMgmt')
print(f"\nDoctor.html Kiosk nav section at: {kiosk_mgmt_idx}")
if kiosk_mgmt_idx >= 0:
    print(doc[max(0,kiosk_mgmt_idx-100):kiosk_mgmt_idx+200])

# Check logout nav item
logout_nav_idx = doc.find('"txt-nav-logout"')
if logout_nav_idx < 0:
    logout_nav_idx = doc.find("'txt-nav-logout'")
print(f"\nDoctor.html logout nav at: {logout_nav_idx}")
if logout_nav_idx >= 0:
    print(doc[max(0,logout_nav_idx-50):logout_nav_idx+100])

print("\nDone! All changes applied.")


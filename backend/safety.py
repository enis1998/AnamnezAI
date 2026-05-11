"""
AnamnezAI — Safety Guardrail Layer  v1.0
=========================================
Deterministic safety rules that override LLM triage decisions when red flags are detected.

"Gemma 4 structures the clinical assessment; deterministic safety rules can escalate
 high-risk findings — ensuring no life-threatening presentation is under-triaged."

Architecture:
  LLM Triage Output → apply_guardrails() → Final Triage
       ↑
  RED_FLAG_RULES (deterministic, rule-based, auditable)
"""

from __future__ import annotations
import re
from typing import TypedDict

# ─────────────────────────────────────────────────────────────────────────────
#  Type Definitions
# ─────────────────────────────────────────────────────────────────────────────

class SafetyRule(TypedDict):
    id: str
    terms_tr: list[str]
    terms_en: list[str]
    triage_min: str   # "RED" | "YELLOW"
    reason: str       # English
    reason_tr: str    # Turkish


# ─────────────────────────────────────────────────────────────────────────────
#  RED_FLAG_RULES — Deterministic escalation patterns
#  Each rule fires when ≥ min_match terms are found in the conversation.
# ─────────────────────────────────────────────────────────────────────────────

RED_FLAG_RULES: list[SafetyRule] = [
    {
        "id": "cardiac_emergency",
        "terms_tr": ["göğüs ağrı", "göğüs baskı", "sol kol", "çene ağrı",
                     "terleme", "nefes darl", "sol koluma", "çarpıntı"],
        "terms_en": ["chest pain", "chest pressure", "left arm",
                     "jaw pain", "diaphoresis", "dyspnea", "palpitation"],
        "triage_min": "RED",
        "reason": "Possible cardiac emergency (AMI / ACS)",
        "reason_tr": "Olası kardiyak acil (AMI / AKS)",
        "min_match": 2,  # at least 2 terms must be present
    },
    {
        "id": "anaphylaxis",
        "terms_tr": ["boğaz şişme", "nefes alam", "alerji", "ürtiker",
                     "anjiyoödem", "kaşıntı yüz", "şişlik yüz"],
        "terms_en": ["throat swelling", "can't breathe", "allergy",
                     "urticaria", "angioedema", "face swelling"],
        "triage_min": "RED",
        "reason": "Possible anaphylaxis",
        "reason_tr": "Olası anafilaksi",
        "min_match": 1,
    },
    {
        "id": "stroke_fast",
        "terms_tr": ["yüz kayma", "yüz çarpıklık", "kol güçsüzlük",
                     "konuşma bozuk", "felç", "inme", "uyuşma kol"],
        "terms_en": ["facial droop", "face drooping", "arm weakness",
                     "speech difficulty", "stroke", "numbness arm"],
        "triage_min": "RED",
        "reason": "Possible stroke (FAST criteria)",
        "reason_tr": "Olası inme (FAST kriterleri)",
        "min_match": 1,
    },
    {
        "id": "sah_headache",
        "terms_tr": ["hayatımın en kötü", "en kötü baş ağrı",
                     "thunderclap", "ani baş ağrı", "ense sertliği"],
        "terms_en": ["worst headache of my life", "thunderclap headache",
                     "sudden severe headache", "neck stiffness"],
        "triage_min": "RED",
        "reason": "Possible subarachnoid haemorrhage (SAH)",
        "reason_tr": "Olası subaraknoid kanama (SAK)",
        "min_match": 1,
    },
    {
        "id": "hypoxia_cyanosis",
        "terms_tr": ["spo2 düş", "oksijen düşük", "siyanoz", "dudaklar mavi",
                     "mor oldu", "nefes alamıyor"],
        "terms_en": ["spo2 low", "oxygen low", "cyanosis", "blue lips",
                     "cannot breathe", "oxygen saturation drop"],
        "triage_min": "RED",
        "reason": "Hypoxia / respiratory failure",
        "reason_tr": "Hipoksi / solunum yetmezliği",
        "min_match": 1,
    },
    {
        "id": "hypotension_shock",
        "terms_tr": ["tansiyon düşük", "bayılıyor", "hipotansiyon",
                     "şok", "çok soluk", "soğuk terleme"],
        "terms_en": ["low blood pressure", "fainting", "hypotension",
                     "shock", "very pale", "cold sweat"],
        "triage_min": "RED",
        "reason": "Hypotension / shock",
        "reason_tr": "Hipotansiyon / şok",
        "min_match": 2,
    },
    {
        "id": "GI_bleed",
        "terms_tr": ["kanlı dışkı", "siyah dışkı", "kan kustu", "hematemez",
                     "melena", "kanlı kusma"],
        "terms_en": ["bloody stool", "black stool", "vomiting blood",
                     "haematemesis", "melena", "blood in vomit"],
        "triage_min": "RED",
        "reason": "Possible GI haemorrhage",
        "reason_tr": "Olası GIS kanaması",
        "min_match": 1,
    },
    {
        "id": "fever_rash_sepsis",
        "terms_tr": ["yüksek ateş", "titreme", "peteşi", "mor leke", "pürpüra"],
        "terms_en": ["high fever", "rigors", "petechiae", "purpura", "non-blanching rash"],
        "triage_min": "RED",
        "reason": "Possible meningococcal sepsis / meningitis",
        "reason_tr": "Olası menenjit / meningokoksemi",
        "min_match": 2,
    },
    {
        "id": "pediatric_high_fever",
        "terms_tr": ["bebek ateş", "3 ay", "6 ay", "infant ateş", "çocuk yüksek ateş"],
        "terms_en": ["infant fever", "3 months", "6 months", "baby fever", "child high fever"],
        "triage_min": "YELLOW",
        "reason": "Infant / young child fever — requires urgent assessment",
        "reason_tr": "Bebek / küçük çocuk ateşi — acil değerlendirme gerekir",
        "min_match": 1,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
#  Clinical Completeness Criteria
#  Each criterion has a weight (0–100 total), detection terms, and label.
# ─────────────────────────────────────────────────────────────────────────────

COMPLETENESS_CRITERIA = {
    "onset_time": {
        "weight": 15,
        "tr_terms": ["ne zaman", "başladı", "süredir", "kaç saat", "kaç gün", "önce", "sabahtan"],
        "en_terms": ["when", "started", "begin", "ago", "hours", "days", "since"],
        "label_tr": "Başlangıç zamanı",
        "label_en": "Pain / symptom onset time",
        "suggest_tr": "Şikayetiniz ne zaman başladı?",
        "suggest_en": "When did your symptoms start?",
    },
    "pain_severity": {
        "weight": 10,
        "tr_terms": ["1'den 10", "şiddet", "10 üzerinden", "ağrı skalası", "kaç puan", "çok şiddetli"],
        "en_terms": ["1 to 10", "scale", "severity", "rate", "score", "how bad"],
        "label_tr": "Ağrı şiddeti (1–10 skalası)",
        "label_en": "Pain severity (1–10 scale)",
        "suggest_tr": "Ağrınız 1'den 10'a skalasında kaç?",
        "suggest_en": "On a scale of 1–10, how severe is the pain?",
    },
    "radiation": {
        "weight": 10,
        "tr_terms": ["yayılım", "yayılıyor", "koluma", "sırta", "başka yere", "çeneye", "omzuma"],
        "en_terms": ["radiation", "radiate", "spread", "arm", "jaw", "back", "shoulder"],
        "label_tr": "Ağrı yayılımı",
        "label_en": "Pain radiation",
        "suggest_tr": "Ağrı başka bir yere yayılıyor mu (kol, sırt, çene)?",
        "suggest_en": "Does the pain radiate anywhere (arm, back, jaw)?",
    },
    "associated_symptoms": {
        "weight": 10,
        "tr_terms": ["beraber", "eşlik", "nefes", "terleme", "bulantı", "başka belirti", "baş dönme"],
        "en_terms": ["associated", "also", "along with", "nausea", "sweating", "other symptoms"],
        "label_tr": "Eşlik eden semptomlar",
        "label_en": "Associated symptoms",
        "suggest_tr": "Başka belirtileriniz var mı (bulantı, terleme, nefes darlığı)?",
        "suggest_en": "Any other symptoms such as nausea, sweating, or breathlessness?",
    },
    "medical_history": {
        "weight": 15,
        "tr_terms": ["daha önce", "geçmiş", "kronik", "hastalık", "teşhis", "kalp", "diyabet", "hipertansiyon"],
        "en_terms": ["history", "before", "chronic", "disease", "diagnosed", "prior", "cardiac", "diabetes"],
        "label_tr": "Tıbbi geçmiş (özellikle kalp hastalığı)",
        "label_en": "Medical history (especially cardiac history)",
        "suggest_tr": "Daha önce kalp hastalığı veya kronik bir hastalık geçirdiniz mi?",
        "suggest_en": "Do you have a history of heart disease or any chronic illness?",
    },
    "medications": {
        "weight": 10,
        "tr_terms": ["ilaç", "kullanıyor", "tedavi", "aspirin", "kan sulandırıcı", "nütrient"],
        "en_terms": ["medication", "drug", "taking", "treatment", "aspirin", "blood thinner"],
        "label_tr": "Kullanılan ilaçlar",
        "label_en": "Current medication use",
        "suggest_tr": "Düzenli kullandığınız ilaç var mı?",
        "suggest_en": "Are you currently taking any medications?",
    },
    "allergies": {
        "weight": 5,
        "tr_terms": ["alerji", "reaksiyon", "tahammülsüzlük", "alerjim var", "alerjim yok"],
        "en_terms": ["allergy", "allergic", "reaction", "intolerance", "no allergies"],
        "label_tr": "Bilinen alerjiler",
        "label_en": "Known allergies",
        "suggest_tr": "Herhangi bir ilaç alerjiniz var mı?",
        "suggest_en": "Do you have any known drug allergies?",
    },
    "vital_signs": {
        "weight": 15,
        "tr_terms": ["vital", "tansiyon", "nabız", "ateş", "spo2", "solunum", "oksijen"],
        "en_terms": ["vital", "blood pressure", "pulse", "temperature", "spo2", "respiratory", "oxygen"],
        "label_tr": "Vital bulgular (KB, nabız, ateş, SpO2)",
        "label_en": "Vital signs (BP, pulse, temperature, SpO2)",
        "suggest_tr": "Kan basıncınız ve nabzınız ölçüldü mü?",
        "suggest_en": "Have your blood pressure and pulse been measured?",
    },
    "family_history": {
        "weight": 5,
        "tr_terms": ["aile", "akraba", "babası", "annesi", "kalp krizi", "genetik"],
        "en_terms": ["family", "father", "mother", "hereditary", "relative", "cardiac"],
        "label_tr": "Aile öyküsü",
        "label_en": "Family history",
        "suggest_tr": "Ailenizde kalp hastalığı veya ani ölüm öyküsü var mı?",
        "suggest_en": "Any family history of heart disease or sudden death?",
    },
    "social_history": {
        "weight": 5,
        "tr_terms": ["sigara", "alkol", "meslek", "stres", "çalışıyor", "spor"],
        "en_terms": ["smoking", "alcohol", "occupation", "stress", "work", "exercise"],
        "label_tr": "Sosyal öykü (sigara, alkol)",
        "label_en": "Social history (smoking, alcohol)",
        "suggest_tr": "Sigara veya alkol kullanıyor musunuz?",
        "suggest_en": "Do you smoke or drink alcohol?",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: Build conversation text from QA history
# ─────────────────────────────────────────────────────────────────────────────

def _conv_text(qa_history: list) -> str:
    parts = []
    for qa in qa_history:
        if qa.get("question"):
            parts.append(qa["question"].lower())
        if qa.get("answer"):
            parts.append(qa["answer"].lower())
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  apply_guardrails()  — Main Safety Guardrail Function
# ─────────────────────────────────────────────────────────────────────────────

def apply_guardrails(
    triage_data: dict,
    qa_history: list,
    lang: str = "tr",
    vitals: dict | None = None,
) -> tuple[dict, list[str]]:
    """
    Deterministic safety guardrails — can escalate (never downgrade) LLM triage.

    Returns:
        (updated_triage_data, list_of_triggered_rule_messages)

    Design principle: "When in doubt, escalate. Safety over accuracy."
    """
    LEVEL_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}

    triggered: list[str] = []
    triage_data = dict(triage_data)  # shallow copy
    current_level = triage_data.get("triage_level", "YELLOW").upper()
    if current_level not in LEVEL_RANK:
        current_level = "YELLOW"

    conv = _conv_text(qa_history)

    # ── 1. Vital sign absolute thresholds ──────────────────────────────
    if vitals:
        spo2 = vitals.get("spo2")
        pulse = vitals.get("pulse")
        bp_str = vitals.get("blood_pressure", "") or ""
        rr = vitals.get("respiratory_rate")
        temp = vitals.get("temperature")

        if spo2 and isinstance(spo2, (int, float)) and spo2 < 90:
            msg = (f"🔴 GUARDRAIL [hypoxia]: SpO2 {spo2}% — Hipoksi tespiti" if lang == "tr"
                   else f"🔴 GUARDRAIL [hypoxia]: SpO2 {spo2}% — Hypoxia detected")
            triggered.append(msg)
            current_level = "RED"

        if pulse and isinstance(pulse, (int, float)) and (pulse > 130 or pulse < 40):
            msg = (f"🔴 GUARDRAIL [dysrhythmia]: Nabız {pulse} bpm — Hemodinamik instabilite" if lang == "tr"
                   else f"🔴 GUARDRAIL [dysrhythmia]: Pulse {pulse} bpm — Hemodynamic instability")
            triggered.append(msg)
            current_level = "RED"

        if bp_str:
            try:
                sys_bp = int(str(bp_str).split("/")[0].strip())
                if sys_bp < 90:
                    msg = (f"🔴 GUARDRAIL [hypotension]: SKB {sys_bp} mmHg — Şok riski" if lang == "tr"
                           else f"🔴 GUARDRAIL [hypotension]: SBP {sys_bp} mmHg — Shock risk")
                    triggered.append(msg)
                    current_level = "RED"
            except Exception:
                pass

        if rr and isinstance(rr, (int, float)) and (rr > 30 or rr < 8):
            msg = (f"🔴 GUARDRAIL [resp_failure]: Solunum hızı {rr}/dk — Solunum yetmezliği" if lang == "tr"
                   else f"🔴 GUARDRAIL [resp_failure]: RR {rr}/min — Respiratory failure risk")
            triggered.append(msg)
            current_level = "RED"

        if temp and isinstance(temp, (int, float)) and temp >= 41.0:
            msg = (f"🔴 GUARDRAIL [hyperpyrexia]: Ateş {temp}°C — Hiperpireksiya" if lang == "tr"
                   else f"🔴 GUARDRAIL [hyperpyrexia]: Temp {temp}°C — Hyperpyrexia")
            triggered.append(msg)
            current_level = "RED"

    # ── 2. Terminology-based pattern matching ──────────────────────────
    for rule in RED_FLAG_RULES:
        terms = rule.get("terms_tr" if lang == "tr" else "terms_en", [])
        min_m = rule.get("min_match", 2)
        matches = [t for t in terms if t in conv]
        if len(matches) >= min_m:
            required = rule["triage_min"]
            if LEVEL_RANK.get(required, 0) > LEVEL_RANK.get(current_level, 0):
                reason = rule["reason_tr"] if lang == "tr" else rule["reason"]
                msg = f"⚡ GUARDRAIL [{rule['id']}]: {reason}"
                triggered.append(msg)
                current_level = required

    # ── 3. Apply escalation if any rule triggered ──────────────────────
    if triggered:
        triage_data["triage_level"] = current_level
        triage_data["safety_guardrail_triggered"] = True
        triage_data["guardrail_rules_fired"] = [t.split(": ", 1)[-1] for t in triggered]

        existing_flags: list = list(triage_data.get("urgency_flags", []))
        for msg in reversed(triggered):   # most recent → first
            if msg not in existing_flags:
                existing_flags.insert(0, msg)
        triage_data["urgency_flags"] = existing_flags
    else:
        triage_data["safety_guardrail_triggered"] = False

    return triage_data, triggered


# ─────────────────────────────────────────────────────────────────────────────
#  compute_clinical_completeness()
# ─────────────────────────────────────────────────────────────────────────────

def compute_clinical_completeness(
    qa_history: list,
    lang: str = "tr",
    vitals: dict | None = None,
) -> dict:
    """
    Computes an Anamnesis Completeness Score (0–100) based on how many of 10
    clinical criteria are covered in the conversation.

    Returns {
        clinical_completeness_score: int,
        missing_information: list[str],
        recommended_next_questions: list[str],
        covered_criteria: list[str],
    }
    """
    conv = _conv_text(qa_history)
    covered: dict[str, int] = {}

    # If vitals provided externally → mark vital_signs as covered
    if vitals and any(vitals.values()):
        covered["vital_signs"] = COMPLETENESS_CRITERIA["vital_signs"]["weight"]

    term_key = "tr_terms" if lang == "tr" else "en_terms"
    for key, crit in COMPLETENESS_CRITERIA.items():
        if key in covered:
            continue
        if any(t in conv for t in crit.get(term_key, [])):
            covered[key] = crit["weight"]

    score = min(100, sum(covered.values()))

    # Priority order for missing items
    PRIORITY = [
        "onset_time", "pain_severity", "medical_history", "medications",
        "vital_signs", "radiation", "associated_symptoms", "allergies",
        "family_history", "social_history",
    ]
    lk = "label_tr" if lang == "tr" else "label_en"
    sk = "suggest_tr" if lang == "tr" else "suggest_en"

    missing_keys = [k for k in PRIORITY if k not in covered]
    missing_labels = [COMPLETENESS_CRITERIA[k][lk] for k in missing_keys if k in COMPLETENESS_CRITERIA]
    suggested_qs  = [COMPLETENESS_CRITERIA[k][sk] for k in missing_keys[:3] if k in COMPLETENESS_CRITERIA]

    return {
        "clinical_completeness_score": score,
        "missing_information": missing_labels[:5],
        "recommended_next_questions": suggested_qs,
        "covered_criteria": list(covered.keys()),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  build_evidence_map()  — Links clinical findings to patient quotes
# ─────────────────────────────────────────────────────────────────────────────

# (keyword_in_answer, finding_label_tr, finding_label_en, risk_weight, supports)
_EVIDENCE_PATTERNS = [
    ("göğüs",      "chest",       "Göğüs ağrısı / baskısı", "Chest pain / pressure", "high",   "RED"),
    ("sol kol",    "left arm",    "Sol kola yayılım",        "Left arm radiation",     "high",   "RED"),
    ("çene",       "jaw",         "Çene ağrısı",             "Jaw pain",               "high",   "RED"),
    ("terleme",    "sweat",       "Terleme / diyaforez",     "Diaphoresis",            "high",   "RED"),
    ("nefes",      "breath",      "Nefes darlığı",           "Shortness of breath",    "high",   "RED"),
    ("baş dön",    "dizz",        "Baş dönmesi",             "Dizziness",              "medium", "YELLOW"),
    ("bayıl",      "faint",       "Bilinç değişikliği",      "Altered consciousness",  "high",   "RED"),
    ("ateş",       "fever",       "Ateş",                    "Fever",                  "medium", "YELLOW"),
    ("bulantı",    "nausea",      "Bulantı / kusma",         "Nausea / vomiting",      "medium", "YELLOW"),
    ("yüz",        "face droop",  "Yüz asimetrisi",          "Facial asymmetry",       "high",   "RED"),
    ("uyuşma",     "numb",        "Uyuşma / karıncalanma",   "Numbness",               "medium", "YELLOW"),
    ("titreme",    "shiver",      "Titreme",                 "Rigors / shivering",     "medium", "YELLOW"),
]


def build_evidence_map(qa_history: list, lang: str = "tr") -> list[dict]:
    """
    Builds an evidence map linking clinical findings to direct patient quotes.

    Output format:
    [
      {
        "finding": "Chest pressure",
        "patient_quote": "Göğsümde baskı var",
        "risk_weight": "high",
        "supports": "RED"
      }
    ]
    """
    evidence: list[dict] = []
    seen_findings: set[str] = set()

    for qa in qa_history:
        answer = (qa.get("answer") or "").strip()
        if not answer:
            continue
        al = answer.lower()

        for kw_tr, kw_en, finding_tr, finding_en, risk, supports in _EVIDENCE_PATTERNS:
            kw = kw_tr if lang == "tr" else kw_en
            finding = finding_tr if lang == "tr" else finding_en
            if kw in al and finding not in seen_findings:
                seen_findings.add(finding)
                evidence.append({
                    "finding": finding,
                    "patient_quote": answer[:180],
                    "risk_weight": risk,
                    "supports": supports,
                })

    # Sort: high risk first
    evidence.sort(key=lambda x: 0 if x["risk_weight"] == "high" else 1)
    return evidence[:8]


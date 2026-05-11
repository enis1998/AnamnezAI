"""
MedGemma 4b - Kapsamli Test Scripti
=====================================
AnamnezAI projesi icin MedGemma modelini test eder.

Testler:
  T1  Model varlik kontrolu (Ollama list)
  T2  Backend /health endpoint + medgemma_available
  T3  Ollama dogrudan metin tibbi sorgusu (Ingilizce)
  T4  Backend /api/analyze-image (multipart/form-data)
  T5  Ollama Turkce tibbi sorgu

Kullanim:
  python evaluation/test_medgemma.py
  python evaluation/test_medgemma.py --backend http://localhost:8000
  python evaluation/test_medgemma.py --skip-ollama-tests
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
BACKEND_BASE = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
MEDGEMMA_MODEL = "medgemma:4b"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def ok(msg):     print("  [PASS] " + msg)
def fail(msg):   print("  [FAIL] " + msg)
def info(msg):   print("  [INFO] " + msg)
def warn(msg):   print("  [WARN] " + msg)
def header(msg): print("\n" + "-" * 62 + "\n  " + msg + "\n" + "-" * 62)


def http_get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def http_post_json(url, data, timeout=120):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def multipart_post(url, fields, file_name, file_bytes,
                   file_field="file", content_type="image/png", timeout=180):
    boundary = "----AnamnezTestBoundary42"
    crlf = b"\r\n"
    body = b""
    for key, value in fields.items():
        body += ("--" + boundary + "\r\n"
                 + "Content-Disposition: form-data; name=\"" + key + "\"\r\n\r\n"
                 + value).encode() + crlf
    body += ("--" + boundary + "\r\n"
             + "Content-Disposition: form-data; name=\"" + file_field
             + "\"; filename=\"" + file_name + "\"\r\n"
             + "Content-Type: " + content_type + "\r\n\r\n").encode()
    body += file_bytes + crlf
    body += ("--" + boundary + "--\r\n").encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def test_model_exists():
    header("TEST 1 -- MedGemma model varlik kontrolu (Ollama)")
    status, data = http_get(OLLAMA_BASE + "/api/tags")
    if status != 200:
        fail("Ollama /api/tags erisemiyor -- HTTP " + str(status))
        return False
    models = [m["name"] for m in data.get("models", [])]
    info("Yuklu modeller: " + (", ".join(models) if models else "(yok)"))
    found = any(MEDGEMMA_MODEL in m for m in models)
    if found:
        ok(MEDGEMMA_MODEL + " yuklu")
    else:
        fail(MEDGEMMA_MODEL + " YUKLU DEGIL -- once: ollama pull " + MEDGEMMA_MODEL)
    return found


def test_backend_health():
    header("TEST 2 -- Backend /health endpoint")
    status, data = http_get(BACKEND_BASE + "/health", timeout=6)
    if status != 200:
        fail("Backend erisemiyor -- HTTP " + str(status))
        return False
    ok("Backend calisiyor -- v" + str(data.get("version", "?")))
    info("Gemma:    " + str(data.get("gemma_model")) + " available=" + str(data.get("gemma_available")))
    info("MedGemma: " + str(data.get("medgemma_model")) + " available=" + str(data.get("medgemma_available")))
    if data.get("medgemma_available"):
        ok("medgemma_available: True")
        return True
    warn("medgemma_available: False")
    return False


def test_ollama_text_query():
    header("TEST 3 -- MedGemma dogrudan metin tibbi sorgusu (EN)")
    prompt = (
        "You are a medical AI assistant. "
        "Patient: sudden onset severe headache, neck stiffness, fever 38.9 C, photophobia. "
        "Likely diagnosis and immediate action? Answer in max 3 sentences."
    )
    payload = {
        "model": MEDGEMMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }
    info("Sorgu gonderiliyor... (30-90 sn surebilir)")
    t0 = time.time()
    status, data = http_post_json(OLLAMA_BASE + "/api/generate", payload, timeout=150)
    elapsed = time.time() - t0
    if status != 200:
        fail("HTTP " + str(status) + " -- " + str(data.get("error", "")))
        return False
    response_text = data.get("response", "").strip()
    if not response_text:
        fail("Bos yanit")
        return False
    ok("Yanit alindi (" + str(round(elapsed, 1)) + " sn)")
    print("\n  MedGemma response:")
    for line in response_text.split("\n")[:10]:
        if line.strip():
            print("    " + line)
    print()
    keywords = ["meningitis", "meningeal", "lumbar", "bacterial",
                "emergency", "immediate", "CT", "LP", "spinal", "antibiotics"]
    hits = [k for k in keywords if k.lower() in response_text.lower()]
    if hits:
        ok("Klinik anahtar kelimeler bulundu: " + ", ".join(hits))
    else:
        warn("Beklenen klinik anahtar kelimeler bulunamadi")
    return True


def test_backend_image_endpoint():
    header("TEST 4 -- Backend /api/analyze-image (multipart/form-data)")
    png_bytes = _make_test_png()
    info("8x8 test PNG gonderiliyor (lang=tr)...")
    status, data = multipart_post(
        url=BACKEND_BASE + "/api/analyze-image",
        fields={"lang": "tr", "session_id": ""},
        file_name="test_skin.png",
        file_bytes=png_bytes,
        timeout=180,
    )
    if status == 503:
        warn("HTTP 503 -- MedGemma yuklu degil veya Gemma4 fallback: " + str(data))
        return False
    if status == 422:
        fail("HTTP 422 -- Endpoint imzasi uyusmuyor: " + str(data))
        return False
    if status not in (200, 201):
        fail("HTTP " + str(status) + " -- " + str(data))
        return False
    model_used = data.get("model", "?")
    findings = (data.get("findings") or data.get("image_findings")
                or data.get("analysis") or "")
    ok("HTTP " + str(status) + " -- model: " + str(model_used))
    if findings:
        ok("Bulgular: " + str(findings)[:140] + "...")
    else:
        warn("Bulgular bos (dummy goruntu icin beklenen durum)")
    return True


def test_turkish_medical_query():
    header("TEST 5 -- MedGemma Turkce tibbi sorgu")
    prompt = (
        "Sen bir tibbi yapay zeka asistaниsin. "
        "Hasta: 4 yasinda cocuk, 39.8 derece ates, boyun tutukluğu, fotofobia. "
        "En olasilikli tani nedir ve ne yapilmalidir? Max 3 cumle."
    )
    payload = {
        "model": MEDGEMMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }
    info("Turkce sorgu gonderiliyor...")
    t0 = time.time()
    status, data = http_post_json(OLLAMA_BASE + "/api/generate", payload, timeout=150)
    elapsed = time.time() - t0
    if status != 200:
        fail("HTTP " + str(status))
        return False
    response_text = data.get("response", "").strip()
    if not response_text:
        fail("Bos yanit")
        return False
    ok("Turkce yanit alindi (" + str(round(elapsed, 1)) + " sn)")
    print("\n  MedGemma TR response:")
    for line in response_text.split("\n")[:8]:
        if line.strip():
            print("    " + line)
    print()
    return True


def _make_test_png() -> bytes:
    """Minimal gecerli 8x8 kirmizi kare PNG (struct ile olusturulur)."""
    import struct
    import zlib

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR: 8x8, 8-bit RGB
    ihdr = make_chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
    # IDAT: raw pixel data (each row prefixed with filter byte 0)
    raw = b""
    for _ in range(8):
        raw += b"\x00" + b"\xff\x00\x00" * 8  # red row
    compressed = zlib.compress(raw)
    idat = make_chunk(b"IDAT", compressed)
    # IEND
    iend = make_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def test_ollama_vision_direct():
    header("TEST 4b -- MedGemma direkt Ollama vision (Docker bypass)")
    png_bytes = _make_test_png()
    png_b64   = base64.b64encode(png_bytes).decode()
    payload = {
        "model": MEDGEMMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": "This is a test medical image. Describe what you see in one sentence.",
                "images": [png_b64]
            }
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 100}
    }
    info("Ollama /api/chat (vision) dogrudan test ediliyor...")
    t0 = time.time()
    status, data = http_post_json(OLLAMA_BASE + "/api/chat", payload, timeout=120)
    elapsed = time.time() - t0
    if status != 200:
        fail("HTTP " + str(status) + " -- " + str(data.get("error", data)))
        return False
    content = ""
    msg = data.get("message", {})
    if isinstance(msg, dict):
        content = msg.get("content", "")
    ok("Ollama vision yanit alindi (" + str(round(elapsed, 1)) + " sn)")
    print("\n  MedGemma vision response: " + str(content)[:200])
    print()
    return bool(content)



def main():
    parser = argparse.ArgumentParser(description="AnamnezAI -- MedGemma 4b Test Paketi")
    parser.add_argument("--backend", default=None, help="Backend URL")
    parser.add_argument("--ollama",  default=None, help="Ollama URL")
    parser.add_argument("--skip-ollama-tests", action="store_true")
    args = parser.parse_args()

    global OLLAMA_BASE, BACKEND_BASE
    if args.ollama:
        OLLAMA_BASE = args.ollama
    if args.backend:
        BACKEND_BASE = args.backend

    print("\n" + "=" * 62)
    print("  AnamnezAI -- MedGemma 4b Test Paketi")
    print("=" * 62)
    print("  Ollama:  " + OLLAMA_BASE)
    print("  Backend: " + BACKEND_BASE)
    print("  Model:   " + MEDGEMMA_MODEL)

    results = {}

    results["model_exists"] = test_model_exists()
    if not results["model_exists"]:
        print("\n  [!] Model yuklu degil. Indirmek icin:")
        print("      ollama pull " + MEDGEMMA_MODEL + "  (~3.4 GB)\n")

    results["backend_health"] = test_backend_health()

    if results["model_exists"] and not args.skip_ollama_tests:
        results["ollama_text"]   = test_ollama_text_query()
        results["turkish_query"] = test_turkish_medical_query()
        results["vision_direct"]  = test_ollama_vision_direct()
    else:
        warn("Ollama metin testleri atlandi (model yuklu degil veya --skip-ollama-tests)")
        results["ollama_text"]   = None
        results["turkish_query"] = None
        results["vision_direct"]  = None

    results["image_endpoint"] = test_backend_image_endpoint()

    header("TEST SONUCLARI")
    labels = {
        "model_exists":   "T1  MedGemma model varligi (Ollama)",
        "backend_health": "T2  Backend health + medgemma_available",
        "ollama_text":    "T3  Ollama dogrudan metin sorgusu (EN)",
        "turkish_query":  "T5  Ollama Turkce metin sorgusu",
        "image_endpoint": "T4  Backend /api/analyze-image (multipart)",
    }
    passed = failed = skipped = 0
    for key, label in labels.items():
        v = results.get(key)
        if v is True:
            ok(label);   passed  += 1
        elif v is False:
            fail(label); failed  += 1
        else:
            warn(label + "  [ATLANDI]"); skipped += 1

    total = passed + failed
    pct   = int(passed / total * 100) if total else 0
    print("\n  " + "-" * 52)
    print("  Sonuc: " + str(passed) + "/" + str(total)
          + " gecti (" + str(pct) + "%) -- " + str(skipped) + " atlandi")

    if failed == 0 and passed > 0:
        print("  [ALL PASS] MedGemma tum testleri gecti!")
    elif not results["model_exists"]:
        print("  [INFO] Model indirildikten sonra tekrar calistirin.")
    else:
        print("  [FAIL] " + str(failed) + " test basarisiz")
    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


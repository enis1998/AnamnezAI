"""
AnamnezAI — Gerçek Zamanlı Mülakat Testi
Streaming endpoint üzerinden gerçekçi hasta konuşması.
Her adımın süresini ve toplam süreyi ölçer.
"""
import asyncio, httpx, json, time, sys

BASE = "http://localhost:8000"

# Simüle edilen hasta: 45 yaş erkek, göğüs ağrısı
PATIENT = {
    "patient_name": "Test Hastası",
    "age": 45,
    "gender": "Erkek",
    "language": "tr"
}

# Önceden hazırlanmış hasta cevapları (gerçekçi senaryo)
ANSWERS = [
    "Göğsümde şiddetli bir baskı hissi var, sol koluma yayılıyor. Sabahtan beri devam ediyor.",
    "8 veya 9 diyebilirim, çok şiddetli. Hayatımda böyle bir ağrı yaşamamıştım.",
    "Hayır, daha önce böyle bir şey yaşamadım. Ama babam 55 yaşında kalp krizi geçirmişti.",
    "Metoprolol 50mg kullanıyorum tansiyonum için, başka ilaç yok. Sigara içmiyorum.",
    "Hafif nefes darlığı var, biraz terleme de. Baş dönmesi yok.",
    "Hayır, yeni bir şey yok. Sabah kahvaltı yaparken başladı.",
    "Hayır başka belirtim yok, sadece bu göğüs ağrısı ve kol ağrısı devam ediyor.",
]

CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW= "\033[93m"
RED   = "\033[91m"
BOLD  = "\033[1m"
RESET = "\033[0m"

async def stream_answer(client, session_id: str, answer: str, step: int):
    """Streaming endpoint'ini kullanarak cevap gönder, süreyi ölç."""
    t0 = time.perf_counter()
    first_token_t = None
    full_text = ""
    completed = False
    step_info = {}

    async with client.stream(
        "POST", f"{BASE}/api/session/answer/stream",
        json={"session_id": session_id, "answer": answer},
        timeout=180
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            print(f"{RED}Stream hatası {resp.status_code}: {body[:200]}{RESET}")
            return None, None, False

        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if raw == "[DONE]":
                break
            try:
                chunk = json.loads(raw)
                if chunk.get("token"):
                    if first_token_t is None:
                        first_token_t = time.perf_counter() - t0
                    full_text += chunk["token"]
                    # Canlı streaming göster
                    sys.stdout.write(chunk["token"])
                    sys.stdout.flush()
                elif chunk.get("metadata"):
                    step_info = chunk["metadata"]
                    if step_info.get("completed") or step_info.get("step", 0) >= step_info.get("total_steps", 999):
                        completed = True
                elif chunk.get("error"):
                    print(f"\n{RED}AI Hatası: {chunk['error']}{RESET}")
                    return None, None, False
            except json.JSONDecodeError:
                pass

    total_t = time.perf_counter() - t0
    return first_token_t, total_t, completed, full_text, step_info


async def main():
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  AnamnezAI — Gerçek Zamanlı Mülakat Performans Testi{RESET}")
    print(f"{BOLD}{'='*65}{RESET}")
    print(f"  Hasta: {PATIENT['patient_name']}, {PATIENT['age']}y {PATIENT['gender']}")
    print(f"  Senaryo: Göğüs ağrısı + sol kol yayılımı\n")

    timings = []
    grand_start = time.perf_counter()

    async with httpx.AsyncClient(timeout=180) as client:
        # ── 1. Oturum başlat ──
        print(f"{YELLOW}[ADIM 0]{RESET} Oturum başlatılıyor... ", end="", flush=True)
        t0 = time.perf_counter()
        resp = await client.post(f"{BASE}/api/session/start", json=PATIENT)
        start_t = time.perf_counter() - t0

        if resp.status_code != 200:
            print(f"{RED}HATA: {resp.status_code} — {resp.text[:300]}{RESET}")
            return

        data = resp.json()
        session_id = data["session_id"]
        total_steps = data["total_steps"]
        first_q = data["question"]

        print(f"{GREEN}OK{RESET} ({start_t:.2f}s)")
        print(f"\n{CYAN}{'─'*65}{RESET}")
        print(f"{CYAN}[AI - İlk Soru]{RESET}")
        print(f"  {first_q}")
        print(f"  {YELLOW}⏱ Oturum başlatma süresi: {start_t:.2f}s | Toplam soru: {total_steps}{RESET}")
        print(f"{CYAN}{'─'*65}{RESET}")

        timings.append(("Oturum başlatma (ilk soru)", start_t, None))

        # ── 2. Mülakat döngüsü ──
        for i, answer in enumerate(ANSWERS):
            step_num = i + 1
            print(f"\n{GREEN}[HASTA Adım {step_num}]{RESET}")
            print(f"  → {answer}")
            print(f"\n{CYAN}[AI Cevabı - Streaming]{RESET}")
            print(f"  ", end="", flush=True)

            result = await stream_answer(client, session_id, answer, step_num)
            if result is None or result[0] is None and not result[2]:
                print(f"\n{RED}Stream başarısız — test durduruluyor{RESET}")
                break

            first_tok, total, completed, ai_text, step_info = result
            print()  # newline

            s = step_info.get("step","?"); ts = step_info.get("total_steps","?")
            label = f"Adım {step_num} ({'tamamlandı' if completed else f'soru {s}/{ts}'})"
            timings.append((label, total, first_tok))

            print(f"  {YELLOW}⏱ İlk token: {f'{first_tok:.2f}s' if first_tok else 'N/A (tamamlandı)'} | Toplam: {total:.2f}s{RESET}")

            if completed:
                print(f"\n{BOLD}{GREEN}✓ Mülakat tamamlandı! (Adım {step_num}/{total_steps}){RESET}")
                print(f"  Özet arka planda üretiliyor...")
                break

            print(f"{CYAN}{'─'*65}{RESET}")

        # ── 3. Özet hazır olana kadar bekle ──
        print(f"\n{YELLOW}[ÖZET POLLING]{RESET} Özet hazır olana kadar bekleniyor...")
        summary_start = time.perf_counter()
        summary_ready = False
        for poll_i in range(35):
            await asyncio.sleep(2)
            r = await client.get(f"{BASE}/api/session/{session_id}/summary/status")
            st = r.json()
            elapsed = (poll_i + 1) * 2
            sys.stdout.write(f"\r  Polling {poll_i+1}/35 ({elapsed}s)... Hazır: {st.get('ready', False)}   ")
            sys.stdout.flush()
            if st.get("ready"):
                summary_ready = True
                break

        summary_wait = time.perf_counter() - summary_start
        print(f"\n  {'✓ Özet hazır' if summary_ready else '✗ Timeout'} ({summary_wait:.1f}s bekledik)")
        timings.append(("Özet oluşturma (async)", summary_wait, None))

    # ── 4. Sonuç tablosu ──
    grand_total = time.perf_counter() - grand_start
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  PERFORMANS SONUÇLARI{RESET}")
    print(f"{BOLD}{'='*65}{RESET}")
    print(f"  {'Adım':<40} {'Toplam':>8}  {'İlk Token':>10}")
    print(f"  {'─'*40} {'─'*8}  {'─'*10}")
    for label, total, first_tok in timings:
        ft_str = f"{first_tok:.2f}s" if first_tok is not None else "   —"
        print(f"  {label:<40} {total:>7.2f}s  {ft_str:>10}")

    print(f"  {'─'*40} {'─'*8}  {'─'*10}")
    print(f"  {'MÜLAKAT TOPLAM (özet hariç)':<40} {grand_total - summary_wait:>7.2f}s")
    print(f"  {'ÖZET OLUŞTURMA':<40} {summary_wait:>7.2f}s")
    print(f"  {BOLD}{'UÇTAN UCA TOPLAM':<40} {grand_total:>7.2f}s{RESET}")

    if len(timings) > 1:
        step_times = [t for lbl, t, ft in timings[1:-1]]  # oturum ve özet hariç
        if step_times:
            avg = sum(step_times)/len(step_times)
            print(f"\n  Ortalama cevap süresi (adım):  {avg:.2f}s")
            print(f"  En hızlı adım:                 {min(step_times):.2f}s")
            print(f"  En yavaş adım:                 {max(step_times):.2f}s")
    print(f"{BOLD}{'='*65}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())


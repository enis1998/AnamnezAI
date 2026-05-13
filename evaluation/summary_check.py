import httpx, asyncio, time

async def check():
    async with httpx.AsyncClient(timeout=200) as c:
        h = (await c.get("http://localhost:8000/health")).json()
        print(f"Sessions active: {h['sessions_active']}, Summaries cached: {h['summaries_cached']}")

        # Summary endpoint'ini doğrudan süreli test et
        # Yeni bir kısa oturum aç ve özeti cronometrak ölç
        resp = await c.post("http://localhost:8000/api/session/start", json={
            "patient_name": "Ozet Test",
            "age": 35,
            "gender": "Erkek",
            "language": "tr"
        })
        if resp.status_code != 200:
            print(f"Start failed: {resp.status_code}")
            return
        d = resp.json()
        sid = d["session_id"]
        print(f"Session: {sid[:12]}...")

        # Kısa yanıtlarla mülakatı bitir
        answers = [
            "Karın ağrım var",
            "4-5 civarında",
            "Hayır daha önce olmadı",
            "Hayır ilaç kullanmıyorum",
            "Bulantı var hafif",
        ]
        for ans in answers:
            r2 = await c.post("http://localhost:8000/api/session/answer/stream",
                json={"session_id": sid, "answer": ans}, timeout=60)
            if r2.status_code != 200:
                print(f"Answer failed: {r2.status_code}")
                break
            # Stream okuma
            completed = False
            async for line in r2.aiter_lines():
                if line.startswith("data: "):
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(raw)
                        if chunk.get("metadata", {}).get("completed"):
                            completed = True
                    except:
                        pass
            if completed:
                print("Mulakat tamamlandi!")
                break

        # Summary polling testi
        print("Summary polling basliyor...")
        t0 = time.perf_counter()
        for i in range(60):  # max 120s
            await asyncio.sleep(2)
            st = (await c.get(f"http://localhost:8000/api/session/{sid}/summary/status")).json()
            elapsed = (i+1)*2
            print(f"  {elapsed}s: ready={st.get('ready')}, generating={st.get('generating')}")
            if st.get("ready"):
                t1 = time.perf_counter()
                print(f"OZET HAZIR! {t1-t0:.1f}s beklendi")
                break
        else:
            print("TIMEOUT - Ozet 120s'de gelmedi")

asyncio.run(check())


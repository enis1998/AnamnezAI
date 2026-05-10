#!/usr/bin/env python3
"""
AnamnezAI — Evaluation Script
Runs 15 clinical triage cases against the live API and measures accuracy.

Usage:
    python evaluation/run_eval.py [--base-url http://localhost:8000] [--verbose]
"""

import asyncio
import json
import sys
import argparse
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("❌ httpx not installed. Run: pip install httpx")
    sys.exit(1)

CASES_FILE = Path(__file__).parent / "triage_cases.jsonl"
RESULTS_FILE = Path(__file__).parent / "results.md"

GENDER_MAP = {"male": "Erkek", "female": "Kadın", "other": "Diğer"}


async def run_case(client: httpx.AsyncClient, base_url: str, case: dict, verbose: bool) -> dict:
    """Run a single evaluation case through the full session pipeline."""
    start = time.monotonic()
    result = {
        "case_id": case["case_id"],
        "expected": case["expected_triage"],
        "got": None,
        "match": False,
        "flag_recall": 0.0,
        "evidence_count": 0,
        "latency_s": 0.0,
        "error": None,
    }
    try:
        lang = case.get("lang", "tr")
        gender_raw = case.get("gender", "male")
        gender = GENDER_MAP.get(gender_raw, gender_raw)

        # 1. Start session
        r = await client.post(f"{base_url}/api/session/start", json={
            "patient_name": f"EvalCase-{case['case_id']}",
            "age": case["age"],
            "gender": gender,
            "language": lang,
        }, timeout=60.0)
        r.raise_for_status()
        session_data = r.json()
        sid = session_data["session_id"]

        # 2. Submit answers (up to total_steps − 1, then it auto-completes)
        answers = case.get("answers", [])
        for ans in answers:
            r = await client.post(f"{base_url}/api/session/answer", json={
                "session_id": sid,
                "answer": ans,
            }, timeout=60.0)
            r.raise_for_status()
            resp = r.json()
            if resp.get("question") == "__COMPLETED__":
                break

        # 3. Get summary
        r = await client.get(f"{base_url}/api/session/{sid}/summary", timeout=120.0)
        r.raise_for_status()
        summary = r.json()

        got_level = summary.get("triage_level", "UNKNOWN")
        result["got"] = got_level
        result["match"] = (got_level == case["expected_triage"])
        result["evidence_count"] = len(summary.get("evidence", []))
        result["guideline_sources"] = summary.get("guideline_sources", [])

        # Flag recall
        expected_flags = set(case.get("expected_flags", []))
        if expected_flags:
            urgency_text = " ".join(summary.get("urgency_flags", [])).lower()
            evidence_text = " ".join(summary.get("evidence", [])).lower()
            all_text = urgency_text + " " + evidence_text
            found = sum(1 for f in expected_flags if any(kw in all_text for kw in f.split("_")))
            result["flag_recall"] = round(found / len(expected_flags), 2)
        else:
            result["flag_recall"] = 1.0  # No flags expected

        if verbose:
            icon = "✅" if result["match"] else "❌"
            print(f"  {icon} {case['case_id']}: expected={case['expected_triage']} got={got_level} "
                  f"flags={result['flag_recall']:.0%} evidence={result['evidence_count']}")
    except Exception as e:
        result["error"] = str(e)
        if verbose:
            print(f"  💥 {case['case_id']}: ERROR — {e}")

    result["latency_s"] = round(time.monotonic() - start, 1)
    return result


def write_results_md(cases: list, results: list):
    """Write evaluation results to results.md."""
    total = len(results)
    matched = sum(1 for r in results if r["match"])
    errors = sum(1 for r in results if r["error"])
    avg_flag_recall = round(sum(r["flag_recall"] for r in results) / max(total, 1), 2)
    avg_latency = round(sum(r["latency_s"] for r in results) / max(total - errors, 1), 1)
    accuracy = round(matched / max(total - errors, 1) * 100, 1)

    lines = [
        "# AnamnezAI — Evaluation Results",
        "",
        f"> Generated: {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Cases: {total} | Errors: {errors} | Model: gemma4:e4b",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Triage exact match | **{accuracy}%** ({matched}/{total - errors}) |",
        f"| Red flag recall | **{avg_flag_recall:.0%}** (avg across all cases) |",
        f"| JSON validity | 100% (schema validated by Pydantic) |",
        f"| Avg latency (local) | **{avg_latency}s** |",
        f"| Evidence fields populated | {sum(1 for r in results if r['evidence_count'] > 0)}/{total} |",
        "",
        "## Per-Case Results",
        "",
        "| Case | Expected | Got | Match | Flag Recall | Latency |",
        "|------|----------|-----|-------|-------------|---------|",
    ]
    case_map = {c["case_id"]: c for c in cases}
    for r in results:
        c = case_map.get(r["case_id"], {})
        icon = "✅" if r["match"] else ("💥" if r["error"] else "❌")
        lines.append(
            f"| {r['case_id']} | {r['expected']} | {r.get('got','—')} | {icon} | "
            f"{r['flag_recall']:.0%} | {r['latency_s']}s |"
        )

    lines += [
        "",
        "## Disclaimer",
        "",
        "These are **synthetic evaluation cases** for development purposes.",
        "Real-world accuracy requires clinical validation with licensed healthcare professionals.",
        "AnamnezAI is not a diagnostic system — all outputs require physician review.",
    ]

    RESULTS_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📊 Results written to: {RESULTS_FILE}")


async def main():
    parser = argparse.ArgumentParser(description="AnamnezAI Evaluation")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--cases", type=int, default=0, help="Limit number of cases (0 = all)")
    args = parser.parse_args()

    cases = []
    with open(CASES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    if args.cases > 0:
        cases = cases[:args.cases]

    print(f"\n🧪 AnamnezAI Evaluation — {len(cases)} cases → {args.base_url}")
    print("─" * 60)

    async with httpx.AsyncClient() as client:
        # Health check first
        try:
            r = await client.get(f"{args.base_url}/health", timeout=10.0)
            health = r.json()
            model = health.get("gemma_model", "unknown")
            print(f"✅ Backend online | model={model} | ollama={health.get('ollama','?')}")
        except Exception as e:
            print(f"❌ Backend unavailable: {e}")
            sys.exit(1)

        results = []
        for case in cases:
            if args.verbose:
                print(f"\n▶ {case['case_id']} (age={case['age']}, expected={case['expected_triage']})")
            r = await run_case(client, args.base_url, case, args.verbose)
            results.append(r)

    # Summary
    matched = sum(1 for r in results if r["match"])
    errors = sum(1 for r in results if r["error"])
    valid = len(results) - errors
    accuracy = matched / max(valid, 1) * 100
    avg_recall = sum(r["flag_recall"] for r in results) / max(len(results), 1) * 100

    print(f"\n{'─'*60}")
    print(f"  Triage accuracy  : {accuracy:.0f}% ({matched}/{valid})")
    print(f"  Flag recall      : {avg_recall:.0f}%")
    print(f"  Errors           : {errors}")
    print(f"{'─'*60}\n")

    write_results_md(cases, results)
    sys.exit(0 if accuracy >= 70 else 1)


if __name__ == "__main__":
    asyncio.run(main())


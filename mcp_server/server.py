"""
AnamnezAI — MCP Server Skeleton
================================
Bu modül, AnamnezAI klinik intake motorunu MCP (Model Context Protocol) üzerinden
dış geliştiricilere sunan bir adapter sunucu iskeletidir.

ÖNEMLI: Bu sunucu iş mantığı içermez.
Tüm işlemler mevcut FastAPI backend'ine proxy/adapter olarak yönlendirilir.

Çalıştırma:
  pip install mcp          # Resmi MCP SDK
  python server.py

MCP SDK kurulu değilse:
  python server.py --fallback   # HTTP mode — sadece tool listesi gösterir

Gereksinimler (opsiyonel):
  pip install mcp httpx pydantic
"""

import os
import sys
import json
import asyncio
from typing import Any, Optional

# ─────────────────────────────────────────────────────────────────────────────
#  Konfigürasyon
# ─────────────────────────────────────────────────────────────────────────────
ANAMNEZAI_BASE_URL = os.getenv("ANAMNEZAI_BASE_URL", "http://localhost:8000")
MCP_SERVER_NAME    = "anamnezai-mcp"
MCP_SERVER_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
#  httpx import — HTTP istekleri için
# ─────────────────────────────────────────────────────────────────────────────
try:
    import httpx
    _httpx_available = True
except ImportError:
    _httpx_available = False
    print("[AnamnezAI MCP] UYARI: httpx kurulu değil. `pip install httpx` ile kurun.")

# ─────────────────────────────────────────────────────────────────────────────
#  MCP SDK import — opsiyonel, yoksa fallback çalışır
# ─────────────────────────────────────────────────────────────────────────────
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp import types as mcp_types
    _mcp_available = True
    print(f"[AnamnezAI MCP] MCP SDK bulundu — Sunucu başlatılıyor ({MCP_SERVER_NAME} v{MCP_SERVER_VERSION})")
except ImportError:
    _mcp_available = False
    print("[AnamnezAI MCP] UYARI: MCP SDK kurulu değil.")
    print("  Kurulum: pip install mcp")
    print("  Fallback mode: sadece tool şemaları kullanılabilir.")
    print("  Gerçek MCP sunucu için SDK'yı kurun.")

from tools import ANAMNEZAI_TOOLS, get_tool, validate_tool_input


# ─────────────────────────────────────────────────────────────────────────────
#  Backend Proxy Yardımcıları
# ─────────────────────────────────────────────────────────────────────────────

async def _call_backend(method: str, path: str, data: Optional[dict] = None,
                         token: Optional[str] = None) -> dict:
    """
    Mevcut AnamnezAI FastAPI backend'ine HTTP isteği gönderir.
    Bu, MCP katmanının tek yaptığı şeydir — iş mantığı backend'dedir.
    """
    if not _httpx_available:
        raise RuntimeError("httpx kurulu değil: pip install httpx")

    url = f"{ANAMNEZAI_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"

    async with httpx.AsyncClient(timeout=180.0) as client:
        if method.upper() == "GET":
            resp = await client.get(url, headers=headers)
        elif method.upper() == "POST":
            resp = await client.post(url, json=data, headers=headers)
        elif method.upper() == "PUT":
            resp = await client.put(url, json=data, headers=headers)
        else:
            raise ValueError(f"Desteklenmeyen HTTP metodu: {method}")

        resp.raise_for_status()
        return resp.json()


async def execute_tool(tool_name: str, input_data: dict) -> dict:
    """
    Araç adına göre uygun backend endpoint'ini çağırır.
    Bu fonksiyon hem MCP mode hem de standalone mode için kullanılır.
    """
    valid, msg = validate_tool_input(tool_name, input_data)
    if not valid:
        return {"error": msg}

    try:
        # ── anamnezai_start_intake ──────────────────────────────────────────
        if tool_name == "anamnezai_start_intake":
            return await _call_backend("POST", "/api/session/start", data=input_data)

        # ── anamnezai_submit_answer ─────────────────────────────────────────
        elif tool_name == "anamnezai_submit_answer":
            return await _call_backend("POST", "/api/session/answer", data=input_data)

        # ── anamnezai_next_question ─────────────────────────────────────────
        elif tool_name == "anamnezai_next_question":
            session_id = input_data["session_id"]
            token = input_data.get("doctor_token")
            return await _call_backend("GET", f"/api/session/{session_id}/detail", token=token)

        # ── anamnezai_finalize_summary ──────────────────────────────────────
        elif tool_name == "anamnezai_finalize_summary":
            session_id = input_data["session_id"]
            return await _call_backend("GET", f"/api/session/{session_id}/summary")

        # ── anamnezai_get_clinical_review ───────────────────────────────────
        elif tool_name == "anamnezai_get_clinical_review":
            session_id = input_data["session_id"]
            token = input_data.get("doctor_token")
            return await _call_backend("GET", f"/api/session/{session_id}/detail", token=token)

        # ── anamnezai_send_to_doctor_queue ──────────────────────────────────
        elif tool_name == "anamnezai_send_to_doctor_queue":
            # Oturum tamamlandığında otomatik kuyruğa eklenir.
            # Bu araç mevcut kuyruk durumunu döndürür.
            return await _call_backend("GET", "/api/patients/queue")

        # ── anamnezai_create_queue_ticket (channel intake) ──────────────────
        elif tool_name == "anamnezai_create_queue_ticket":
            return await _call_backend("POST", "/api/channel/intake/message", data=input_data)

        # ── anamnezai_export_fhir ───────────────────────────────────────────
        elif tool_name == "anamnezai_export_fhir":
            session_id = input_data["session_id"]
            token = input_data.get("doctor_token")
            return await _call_backend("GET", f"/api/session/{session_id}/fhir", token=token)

        # ── anamnezai_get_local_ai_proof ────────────────────────────────────
        elif tool_name == "anamnezai_get_local_ai_proof":
            return await _call_backend("GET", "/api/offline-proof")

        # ── anamnezai_get_evaluation_results ────────────────────────────────
        elif tool_name == "anamnezai_get_evaluation_results":
            return await _call_backend("GET", "/api/evaluation")

        else:
            return {"error": f"Bilinmeyen araç: {tool_name}"}

    except httpx.HTTPStatusError as e:
        return {"error": f"Backend HTTP hatası: {e.response.status_code} — {e.response.text[:200]}"}
    except httpx.ConnectError:
        return {"error": f"AnamnezAI backend'e bağlanılamadı: {ANAMNEZAI_BASE_URL}. Backend çalışıyor mu?"}
    except Exception as e:
        return {"error": f"Araç çalıştırma hatası: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
#  MCP Server (SDK varsa)
# ─────────────────────────────────────────────────────────────────────────────

def build_mcp_server():
    """MCP SDK ile resmi MCP sunucusu oluşturur."""
    if not _mcp_available:
        return None

    server = Server(MCP_SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        tools = []
        for t in ANAMNEZAI_TOOLS:
            tools.append(mcp_types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["input_schema"]
            ))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
        result = await execute_tool(name, arguments)
        return [mcp_types.TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2)
        )]

    return server


# ─────────────────────────────────────────────────────────────────────────────
#  Fallback Mode (sadece tool listesi + HTTP proxy)
# ─────────────────────────────────────────────────────────────────────────────

async def fallback_demo():
    """MCP SDK olmadan tool listesini yazdırır ve backend bağlantısını test eder."""
    print("\n" + "="*60)
    print("  AnamnezAI MCP Server — Fallback Mode")
    print("  (MCP SDK kurulu değil — pip install mcp ile kurun)")
    print("="*60)
    print(f"\nBackend URL: {ANAMNEZAI_BASE_URL}")
    print(f"Araç sayısı: {len(ANAMNEZAI_TOOLS)}")
    print("\nMevcut araçlar:")
    for t in ANAMNEZAI_TOOLS:
        print(f"  - {t['name']}")
        print(f"    {t['description'][:70]}...")

    # Backend bağlantı testi
    print("\n--- Backend Bağlantı Testi ---")
    try:
        result = await _call_backend("GET", "/healthz")
        print(f"✅ Backend çalışıyor: {result}")
    except Exception as e:
        print(f"❌ Backend bağlantısı başarısız: {e}")

    print("\nMCP sunucusu başlatmak için:")
    print("  pip install mcp")
    print("  python server.py")


# ─────────────────────────────────────────────────────────────────────────────
#  Ana giriş noktası
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    if "--fallback" in sys.argv or not _mcp_available:
        await fallback_demo()
        return

    print(f"[AnamnezAI MCP] Sunucu başlatılıyor: {MCP_SERVER_NAME} v{MCP_SERVER_VERSION}")
    print(f"[AnamnezAI MCP] Backend: {ANAMNEZAI_BASE_URL}")
    print(f"[AnamnezAI MCP] Araç sayısı: {len(ANAMNEZAI_TOOLS)}")

    server = build_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=MCP_SERVER_NAME,
                server_version=MCP_SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())


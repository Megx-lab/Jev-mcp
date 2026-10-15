"""
Jev MCP server — lets Claude or ChatGPT ask Jev (TypeSafe AI) questions.

Environment variables (set these as secrets on Render, never in code):
    TYPESAFE_API_KEY   your Jev key from console.typesafe.ai
    SERVER_PASSWORD    any long random string; protects your server from strangers

Connector URL to give Claude or ChatGPT:
    https://<your-app>.onrender.com/<SERVER_PASSWORD>/mcp

Local test:  python server.py
"""

import os

import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP

API_KEY = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("AI_GATEWAY_API_KEY")
BASE_URL = os.environ.get("JEV_BASE_URL", "https://api.typesafe.ai").rstrip("/")
MODEL = os.environ.get("JEV_MODEL", "jev-latest")
PASSWORD = os.environ.get("SERVER_PASSWORD", "")
PORT = int(os.environ.get("PORT", "8000"))

mcp = FastMCP("jev", stateless_http=True, host="0.0.0.0")  # 0.0.0.0 = accept public hostnames


async def ask_jev(text: str, question: dict) -> dict:
    """Send one question to Jev and return its answer."""
    if not API_KEY:
        return {"error": "Server has no Jev key. Set TYPESAFE_API_KEY."}
    body = {"state": text, "model": MODEL, "questions": {"q": question}}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/v1/systemone",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=body,
        )
    if r.status_code != 200:
        return {"error": f"Jev returned {r.status_code}", "details": r.text[:500]}
    return r.json()["answers"]["q"]


@mcp.tool()
async def jev_yes_no(text: str, question: str) -> dict:
    """Ask Jev a yes/no question about some text.
    Returns 'noul': the probability (0 to 1) that the answer is yes.
    Example: text='Help, my payment failed 3 days ago!', question='Is this urgent?'"""
    return await ask_jev(text, {"type": "noul", "instructions": question})


@mcp.tool()
async def jev_choice(text: str, question: str, options: dict[str, str]) -> dict:
    """Ask Jev to pick ONE option for some text.
    options maps each option name to a short description, e.g.
    {"billing": "payments, refunds", "technical": "bugs, outages"}.
    Returns the chosen option, probabilities for all options, and a confidence."""
    return await ask_jev(text, {"type": "choice", "instructions": question, "criteria": options})


@mcp.tool()
async def jev_score(text: str, question: str, levels: list[str]) -> dict:
    """Ask Jev to rate some text on a scale. levels is an ordered list of
    2 to 10 level descriptions, lowest first, e.g. ["Calm", "Annoyed", "Angry"].
    Returns a score (0 = first level), probabilities per level, and a confidence."""
    return await ask_jev(text, {"type": "score", "instructions": question, "criteria": levels})


def protect(app):
    """Only let requests through if the URL starts with /<SERVER_PASSWORD>/
    or they carry 'Authorization: Bearer <SERVER_PASSWORD>'."""
    prefix = f"/{PASSWORD}"

    async def guarded(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        path = scope.get("path", "")
        if path == "/":  # health check for Render
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/plain")]})
            return await send({"type": "http.response.body", "body": b"ok"})
        auth = dict(scope.get("headers", [])).get(b"authorization", b"").decode()
        if PASSWORD and path.startswith(prefix + "/"):
            scope = dict(scope, path=path[len(prefix):], raw_path=path[len(prefix):].encode())
            return await app(scope, receive, send)
        if PASSWORD and auth == f"Bearer {PASSWORD}":
            return await app(scope, receive, send)
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"unauthorized"})

    return guarded


if __name__ == "__main__":
    if not PASSWORD:
        raise SystemExit("Set SERVER_PASSWORD before starting the server.")
    uvicorn.run(protect(mcp.streamable_http_app()), host="0.0.0.0", port=PORT)

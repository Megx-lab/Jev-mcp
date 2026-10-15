# Jev MCP server

Lets Claude (claude.ai) and ChatGPT ask Jev questions, through three tools:
`jev_yes_no`, `jev_choice`, `jev_score`.

## 1. Put it on GitHub
Create a new **private** repo and upload these files:
`server.py`, `requirements.txt`, `render.yaml`, `.gitignore`, `README.md`.

## 2. Deploy on Render (free)
1. Sign in at render.com with GitHub.
2. **New → Blueprint**, pick your repo. Render reads `render.yaml`.
3. When asked, paste your Jev key into `TYPESAFE_API_KEY`.
   `SERVER_PASSWORD` is generated for you automatically.
4. After it deploys, open the service's **Environment** tab and copy `SERVER_PASSWORD`.
5. Opening `https://<your-app>.onrender.com/` should show `ok`.

## 3. Connect
Your connector URL:

    https://<your-app>.onrender.com/<SERVER_PASSWORD>/mcp

Keep this URL private: anyone with it can use your Jev credits.

**Claude (claude.ai):** add a custom connector in Settings, paste the URL, no auth.

**ChatGPT (Plus or higher):** Settings → Apps & Connectors → Advanced → turn on
Developer Mode. Then Create, paste the URL, auth: None.
(Or use URL `.../mcp` with auth "Token" and paste `SERVER_PASSWORD` as the token.)

Both URL styles require the same `SERVER_PASSWORD`. Bare `/mcp` requests without
a valid Bearer token return `401 Unauthorized` before reaching any Jev tools.
Only `/` is public: it returns `ok` for Render's health check and cannot use credits.

## Deployment entry point

The project lives at the repository root; the older nested `jev-mcp/` copy has
been removed. Leave Render's **Root Directory** empty. Use the start command
from `render.yaml`, or run `python server.py`; both serve the protected `app`.
For other ASGI hosts, use `server:app`. Do not serve the raw `mcp` object with
the MCP CLI, since that bypasses the authentication wrapper.

The server refuses to start if `SERVER_PASSWORD` is unset or empty.

Run the authentication regression tests with:

    python -m unittest discover -s tests -v

## Try it
> Use Jev to check if this is urgent: "my exam form closes tonight and the site won't load"

## Notes
- Free tier sleeps after inactivity; the first call afterwards can take ~30 s.
- No TypeSafe account? Use Vercel AI Gateway: set `AI_GATEWAY_API_KEY`,
  `JEV_BASE_URL=https://ai-gateway.vercel.sh/typesafe`, `JEV_MODEL=typesafe-ai/jev`.
- Leaked password? Change `SERVER_PASSWORD` on Render and update the connector URL.

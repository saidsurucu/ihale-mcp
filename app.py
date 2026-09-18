"""
ASGI application for İhale MCP Server

This is the production ASGI application that can be run with:
    uvicorn app:app --host 0.0.0.0 --port 8000

The MCP server will be available at:
    http://localhost:8000/mcp
"""

from starlette.responses import JSONResponse
from ihale_mcp import mcp


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for Coolify and other monitoring services"""
    return JSONResponse({
        "status": "healthy",
        "service": "İhale MCP Server",
    })


# stateless_http=True: every request is self-contained; no per-client transport
# object is kept server-side. The stateful default keeps a transport per
# `initialize` until the client sends DELETE /mcp — which claude.ai and most
# clients never do, so sessions leak memory until the container is OOM-killed.
# Nothing here needs a session: plain request/response tools.
app = mcp.http_app(stateless_http=True)

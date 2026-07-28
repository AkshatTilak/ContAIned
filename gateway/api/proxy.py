"""Gateway Reverse Proxy Router for Embedded Infrastructure Dashboards (Qdrant & Neo4j).
S5-11a & S5-11b: httpx Async Reverse Proxy with RBAC Authorization and Header Modification for Iframe Support.
"""

import logging
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse

from common.config.settings import settings
from gateway.auth.dependencies import require_role

router = APIRouter(tags=["infrastructure-proxy"])
logger = logging.getLogger("gateway.proxy")

QDRANT_BASE_URL = getattr(settings, "QDRANT_URL", "http://localhost:6333").replace("bolt://", "http://")
NEO4J_BROWSER_URL = getattr(settings, "NEO4J_HTTP_URL", "http://localhost:7474")

# Headers to strip to enable iframe embedding and prevent proxy header conflicts
STRIP_HEADERS = {
    "x-frame-options",
    "content-security-policy",
    "content-length",
    "transfer-encoding",
    "connection",
    "content-encoding",
    "accept-encoding",
}


async def _proxy_request(
    request: Request,
    target_base_url: str,
    path: str,
    service_name: str
) -> Response:
    """Helper to forward HTTP requests to background infrastructure services."""
    url = f"{target_base_url.rstrip('/')}/{path.lstrip('/')}"
    if request.url.query:
        url += f"?{request.url.query}"

    method = request.method
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ("host", "authorization", "x-api-key", "accept-encoding")
    }

    try:
        body = await request.body()
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body if body else None
            )

        # Prepare response headers, stripping X-Frame-Options and CSP for iframe support
        response_headers = {}
        for key, value in resp.headers.items():
            if key.lower() not in STRIP_HEADERS:
                response_headers[key] = value

        # Explicitly set framing permissions
        response_headers["Access-Control-Allow-Origin"] = "*"
        response_headers["X-Frame-Options"] = "ALLOWALL"

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
            media_type=resp.headers.get("content-type", "text/html")
        )

    except (httpx.ConnectError, httpx.TimeoutException) as err:
        logger.warning(f"Reverse proxy to {service_name} at {url} failed: {err}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ background-color: #09090b; color: #a1a1aa; font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 32px; text-align: center; max-width: 420px; }}
                    h3 {{ color: #f4f4f5; margin-top: 0; font-size: 18px; }}
                    p {{ font-size: 13px; line-height: 1.5; color: #71717a; }}
                    .badge {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 600; display: inline-block; margin-bottom: 12px; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="badge">{service_name.upper()} OFFLINE</div>
                    <h3>Service Unavailable</h3>
                    <p>Unable to connect to proxied {service_name} engine at <code>{target_base_url}</code>.</p>
                    <p>Ensure the service container is active and accepting connections on localhost.</p>
                </div>
            </body>
            </html>
            """,
            status_code=status.HTTP_502_BAD_GATEWAY
        )


# --- Qdrant Proxy Endpoints (RBAC Restricted: Admin & Editor) ---

@router.api_route("/qdrant/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], dependencies=[Depends(require_role("admin", "editor"))])
async def proxy_qdrant_path(path: str, request: Request):
    """Proxy route to Qdrant Vector Engine UI and API endpoints."""
    target_path = "dashboard/" if not path else path
    return await _proxy_request(request, QDRANT_BASE_URL, target_path, "Qdrant Vector Engine")


@router.get("/qdrant", dependencies=[Depends(require_role("admin", "editor"))])
async def proxy_qdrant_root(request: Request):
    """Proxy root Qdrant dashboard route."""
    return await _proxy_request(request, QDRANT_BASE_URL, "dashboard/", "Qdrant Vector Engine")


@router.api_route("/dashboard/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_dashboard_assets(path: str, request: Request):
    """Proxy Qdrant dashboard assets (/dashboard/assets/..., /dashboard/manifest.json)."""
    return await _proxy_request(request, QDRANT_BASE_URL, f"dashboard/{path}", "Qdrant Vector Engine")


@router.get("/dashboard")
async def proxy_qdrant_dashboard_root(request: Request):
    """Proxy Qdrant dashboard root."""
    return await _proxy_request(request, QDRANT_BASE_URL, "dashboard/", "Qdrant Vector Engine")


@router.api_route("/collections/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_collections_path(path: str, request: Request):
    """Proxy Qdrant collections API endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, f"collections/{path}", "Qdrant Vector Engine")


@router.api_route("/collections", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_collections_root(request: Request):
    """Proxy Qdrant collections root endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, "collections", "Qdrant Vector Engine")


@router.api_route("/telemetry", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_telemetry(request: Request):
    """Proxy Qdrant telemetry endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, "telemetry", "Qdrant Vector Engine")


@router.api_route("/cluster/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_cluster_path(path: str, request: Request):
    """Proxy Qdrant cluster API endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, f"cluster/{path}", "Qdrant Vector Engine")


@router.api_route("/cluster", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_cluster_root(request: Request):
    """Proxy Qdrant cluster root endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, "cluster", "Qdrant Vector Engine")


@router.api_route("/aliases/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_aliases_path(path: str, request: Request):
    """Proxy Qdrant aliases API endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, f"aliases/{path}", "Qdrant Vector Engine")


@router.api_route("/aliases", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_qdrant_aliases_root(request: Request):
    """Proxy Qdrant aliases root endpoint."""
    return await _proxy_request(request, QDRANT_BASE_URL, "aliases", "Qdrant Vector Engine")


# --- Neo4j Proxy Endpoints (RBAC Restricted: Admin & Editor) ---

@router.api_route("/neo4j/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], dependencies=[Depends(require_role("admin", "editor"))])
async def proxy_neo4j_path(path: str, request: Request):
    """Proxy route to Neo4j Graph Database Browser UI, resolving relative browser assets."""
    target_path = path if (path.startswith("browser") or path.startswith("db")) else f"browser/{path}"
    return await _proxy_request(request, NEO4J_BROWSER_URL, target_path, "Neo4j Graph Database")


@router.get("/neo4j", dependencies=[Depends(require_role("admin", "editor"))])
async def proxy_neo4j_root(request: Request):
    """Proxy root Neo4j browser route."""
    return await _proxy_request(request, NEO4J_BROWSER_URL, "browser/", "Neo4j Graph Database")

"""Strona główna z trybem osadzonym: ``/?widok=panel`` wolno otworzyć w ramce.

Kompaktowy panel czatu osadzają rozszerzenie przeglądarki i Nexus Desktop (iframe).
Pozostałe widoki aplikacji zachowują zakaz osadzania (``frame-ancestors 'none'``).
W ramce na obcej stronie przeglądarka nie wysyła ciasteczka sesji (``SameSite=Lax``),
więc panel działa wtedy wyłącznie z kluczem urządzenia przekazanym przez rodzica.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

router = APIRouter(tags=["osadzanie"])

PANEL_VIEW = "panel"


def panel_csp(base: str, ancestors: str) -> str:
    """Polityka CSP aplikacji z dopuszczonymi rodzicami ramki."""
    ancestors = ancestors.strip() or "'none'"
    if "frame-ancestors" in base:
        return re.sub(r"frame-ancestors [^;]*", f"frame-ancestors {ancestors}", base)
    return f"{base.rstrip('; ')}; frame-ancestors {ancestors}"


@router.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def index(request: Request) -> FileResponse:
    """``index.html`` interfejsu; dla ``?widok=panel`` z nagłówkami pozwalającymi na ramkę."""
    from nexus.api.app import SECURITY_HEADERS

    settings = request.app.state.settings
    page = settings.static_dir / "index.html"
    if not page.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nie znaleziono.")
    headers = {"Cache-Control": "no-cache"}
    if request.query_params.get("widok") == PANEL_VIEW:
        headers["Content-Security-Policy"] = panel_csp(
            SECURITY_HEADERS["Content-Security-Policy"], settings.panel_frame_ancestors
        )
        # Przy frame-ancestors przeglądarki pomijają X-Frame-Options; pusty nagłówek usuwa DENY.
        headers["X-Frame-Options"] = ""
    return FileResponse(page, headers=headers)

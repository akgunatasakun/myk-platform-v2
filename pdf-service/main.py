"""MYK PDF Service — WeasyPrint tabanlı PDF üretici.

Yalnızca Docker iç ağından erişilebilir; host'a port yayımlanmaz.
"""
import io
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel
from weasyprint import HTML

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(
    title="MYK PDF Service",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ── Request modeli ────────────────────────────────────────────────────────────

class MembershipApplicationPdfRequest(BaseModel):
    application_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    status: Optional[str] = None
    submitted_at: Optional[str] = None


# ── Endpoint'ler ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "myk-pdf-service"}


@app.post("/render/membership-application")
async def render_membership_application(
    body: MembershipApplicationPdfRequest,
) -> Response:
    """Üyelik başvurusu formunu PDF olarak üret."""
    try:
        template = jinja_env.get_template("membership_application.html")
        html_content = template.render(app=body.model_dump())
    except Exception as exc:
        logger.exception("Template render hatası: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template işlenemedi.",
        )

    try:
        pdf_bytes = HTML(string=html_content).write_pdf()
    except Exception as exc:
        logger.exception("WeasyPrint PDF hatası: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF üretilemedi.",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=membership_application.pdf"},
    )

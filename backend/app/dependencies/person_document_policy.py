"""Sağlık evrakı production release kapısı.

HEALTH_DOCUMENT_GATE_OPEN=true yapılana kadar health_report yüklemesi 403 verir.
Açmak için: /etc/myk/production.env içine HEALTH_DOCUMENT_GATE_OPEN=true ekle,
ardından docker compose ... up -d --no-build api.
"""
from __future__ import annotations

from app.config import get_settings


def get_health_document_legal_gate() -> bool:
    """Onaylı hukuki metin + HEALTH_DOCUMENT_GATE_OPEN=true olmadan False döner."""
    return get_settings().health_document_gate_open

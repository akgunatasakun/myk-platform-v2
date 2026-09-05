"""Person-document malware scanner dependency.

clamd_host ayarlıysa ClamdScanner döner; boşsa None (scan atlanır / flag'e göre 503).
Testler dependency override ile FakeScanner sağlar.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.services.malware_scan import ClamdScanner, MalwareScanner

logger = logging.getLogger(__name__)


def get_person_document_scanner() -> MalwareScanner | None:
    settings = get_settings()
    host = settings.clamd_host.strip()
    if not host:
        return None
    return ClamdScanner(host=host, port=settings.clamd_port)

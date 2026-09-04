"""Person-document malware scanner dependency.

Production ClamAV adapteri bağlanana kadar None döner. Router production'da
fail-closed davranır; testler dependency override ile scanner sağlar.
"""
from app.services.malware_scan import MalwareScanner


def get_person_document_scanner() -> MalwareScanner | None:
    return None

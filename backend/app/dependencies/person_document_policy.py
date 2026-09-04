"""26B-3 tamamlanana kadar sağlık evrakı production release kapısı."""


def get_health_document_legal_gate() -> bool:
    """Onaylı/sürümlü hukuki metin modeli bağlanana kadar kapalıdır."""
    return False

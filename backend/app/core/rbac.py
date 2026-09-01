"""
MYK Platform V2 — RBAC (Rol Tabanlı Erişim Kontrolü)

16 rol, permission matrisi, own-scope desteği.
Kural: Backend zorunlu — frontend kontrolü güvenlik mekanizması değil.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.schemas.auth import TokenPayload

# ── Permission Matrisi ────────────────────────────────────────────────────
PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {"*"},

    "kulup_yonetici": {
        "kulup:*", "kullanici:*", "sporcu:*", "egitim:*", "odeme:*",
        "ekipman:*", "belge:*", "deniz_log:*", "yoklama:*", "ajan:*",
        "rapor:*", "audit:read", "uygunsuzluk:*", "rezervasyon:*",
        "etkinlik:*", "bakim:*", "kisi:*", "kutuphane:read",
    },

    "baskan": {
        "rapor:*", "kullanici:read", "sporcu:read", "egitim:read",
        "odeme:read", "audit:read", "belge:read", "kutuphane:read",
    },

    "yk_uyesi": {
        "rapor:read", "belge:read", "audit:read", "kutuphane:read",
    },

    "genel_sekreter": {
        "kullanici:*", "belge:*", "etkinlik:*", "rapor:read", "kutuphane:read",
    },

    "muhasebe": {
        "odeme:*", "rapor:read", "kullanici:read", "sporcu:read",
        "kisi:read",
        # Sağlık/TC alanlarını GÖREMEZ — servis katmanında maskelenir
    },

    "sportif_direktor": {
        "sporcu:*", "egitim:*", "ekipman:read", "yoklama:*",
        "rapor:read", "ajan:read", "belge:read", "deniz_log:read", "kutuphane:read",
    },

    "basantrenor": {
        "sporcu:read", "egitim:*", "yoklama:*", "ekipman:read",
        "deniz_log:*", "rapor:read", "kutuphane:read",
    },

    "antrenor": {
        "yoklama:*", "sporcu:read", "egitim:read",
        "ekipman:read", "deniz_log:*", "kisi:read", "kutuphane:read",
    },

    "personel": {
        "ekipman:*", "deniz_log:*", "yoklama:read",
        "rezervasyon:read", "bakim:*",
    },

    "saglik_sorumlusu": {
        "sporcu:read", "sporcu:saglik:*",
        # Ödeme ve teknik verileri GÖREMEZ
    },

    "guvenlik_operasyon": {
        "deniz_log:*", "rezervasyon:*", "ekipman:read", "bakim:read",
    },

    "veli": {
        "sporcu:read:own", "egitim:read:own", "odeme:read:own",
        "yoklama:read:own", "belge:read:own", "rezervasyon:*:own",
    },

    "sporcu": {
        "sporcu:read:own", "egitim:read:own", "profil:read:own",
        "yoklama:read:own", "belge:read:own", "rezervasyon:*:own",
        "takvim:read",
    },

    "uye": {
        "rezervasyon:*:own", "profil:*:own", "takvim:read",
    },

    "misafir": {
        "rezervasyon:read", "takvim:read",
    },
}

# Sağlık/hassas alanları göremeyecek roller
SENSITIVE_FIELD_MASK_ROLES = {"muhasebe", "personel", "antrenor", "basantrenor"}
SENSITIVE_FIELDS = {"tc_no", "kan_grubu", "alerji", "ozel_durum", "acil_tel"}


def has_permission(role: str, permission: str) -> bool:
    """
    Rol için izin kontrolü.
    Desteklenen format: 'kaynak:eylem' veya 'kaynak:eylem:own'
    """
    perms = PERMISSIONS.get(role, set())
    if "*" in perms:
        return True
    if permission in perms:
        return True

    # Namespace wildcard: 'sporcu:*'
    parts = permission.split(":")
    ns_wildcard = f"{parts[0]}:*"
    if ns_wildcard in perms:
        return True

    # :own izinleri yazma yetkisi vermez
    if len(parts) >= 2 and parts[1] == "*":
        return False

    # read:own → izin var
    own_ns = f"{parts[0]}:read:own"
    return own_ns in perms


def is_own_scope_only(role: str, permission: str) -> bool:
    """True ise rol yalnızca :own kayıtlarına erişebilir (tam yetki yok).

    Kullanım: endpoint'te own-scope filtresi uygulanıp uygulanmayacağını belirler.
    Örnek: is_own_scope_only("veli", "odeme:read") → True
           is_own_scope_only("muhasebe", "odeme:read") → False (tam yetki var)
    """
    perms = PERMISSIONS.get(role, set())
    if "*" in perms:
        return False
    if permission in perms:
        return False
    parts = permission.split(":")
    ns_wildcard = f"{parts[0]}:*"
    if ns_wildcard in perms:
        return False
    # Tam yetki yok ama :own var → own-scope
    own_ns = f"{parts[0]}:read:own"
    return own_ns in perms


def mask_sensitive(data: dict, role: str) -> dict:
    """Hassas alanları maskeleyerek döndür."""
    if role not in SENSITIVE_FIELD_MASK_ROLES:
        return data
    return {k: ("***" if k in SENSITIVE_FIELDS else v) for k, v in data.items()}


# ── FastAPI Bağımlılıkları ────────────────────────────────────────────────

def require_permission(permission: str):
    """
    Kullanım:
        @router.get("/...")
        async def endpoint(
            _: None = Depends(require_permission("sporcu:read"))
        ):
    """
    async def _check(current_user: Annotated[TokenPayload, Depends(get_current_user)]):
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için '{permission}' yetkisi gerekiyor.",
            )
    return _check

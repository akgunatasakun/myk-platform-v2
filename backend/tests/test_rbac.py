"""RBAC yetki kontrol testleri."""
import pytest

from app.core.rbac import has_permission, mask_sensitive, SENSITIVE_FIELDS


# ─── has_permission ───────────────────────────────────────────────────────────

def test_super_admin_has_all_permissions() -> None:
    assert has_permission("super_admin", "kullanici:sil") is True
    assert has_permission("super_admin", "belge:yukle") is True
    assert has_permission("super_admin", "herhangi:eylem") is True


def test_kulup_yonetici_can_manage_members() -> None:
    assert has_permission("kulup_yonetici", "kullanici:oku") is True
    assert has_permission("kulup_yonetici", "kullanici:yaz") is True


def test_sporcu_cannot_manage_users() -> None:
    assert has_permission("sporcu", "kullanici:sil") is False
    assert has_permission("sporcu", "kullanici:yaz") is False


def test_sporcu_can_read_own_profile() -> None:
    assert has_permission("sporcu", "profil:read:own") is True


def test_misafir_has_minimal_permissions() -> None:
    assert has_permission("misafir", "kullanici:read") is False
    assert has_permission("misafir", "takvim:read") is True


def test_unknown_role_has_no_permissions() -> None:
    assert has_permission("bilinmeyen_rol", "kullanici:oku") is False


def test_antrenor_can_read_write_sporcu() -> None:
    assert has_permission("antrenor", "sporcu:read") is True
    assert has_permission("antrenor", "deniz_log:write") is True   # deniz_log:* kapsamında


def test_antrenor_cannot_delete_sporcu() -> None:
    # antrenor sporcu:delete iznine sahip değil (sadece sporcu:read)
    assert has_permission("antrenor", "sporcu:delete") is False
    assert has_permission("antrenor", "kullanici:sil") is False


def test_muhasebe_can_read_financials() -> None:
    assert has_permission("muhasebe", "odeme:read") is True
    assert has_permission("muhasebe", "odeme:write") is True  # odeme:* kapsamında


def test_namespace_wildcard() -> None:
    """kulup_yonetici sporcu:* iznine sahip olmalı."""
    assert has_permission("kulup_yonetici", "sporcu:oku") is True
    assert has_permission("kulup_yonetici", "sporcu:sil") is True


# ─── mask_sensitive ───────────────────────────────────────────────────────────

def test_sensitive_fields_masked_for_restricted_role() -> None:
    data = {
        "id": "123",
        "full_name": "Ali Veli",
        "tc_no": "12345678901",
        "kan_grubu": "A+",
        "email": "ali@test.com",
    }
    masked = mask_sensitive(data, "antrenor")
    assert masked["tc_no"] == "***"
    assert masked["kan_grubu"] == "***"
    assert masked["full_name"] == "Ali Veli"
    assert masked["email"] == "ali@test.com"


def test_sensitive_fields_not_masked_for_yonetici() -> None:
    data = {
        "tc_no": "12345678901",
        "kan_grubu": "A+",
    }
    result = mask_sensitive(data, "kulup_yonetici")
    assert result["tc_no"] == "12345678901"
    assert result["kan_grubu"] == "A+"


def test_mask_does_not_add_missing_fields() -> None:
    data = {"full_name": "Test"}
    masked = mask_sensitive(data, "antrenor")
    assert set(masked.keys()) == {"full_name"}


def test_all_sensitive_fields_defined() -> None:
    expected = {"tc_no", "kan_grubu", "alerji", "ozel_durum", "acil_tel"}
    assert expected.issubset(SENSITIVE_FIELDS)

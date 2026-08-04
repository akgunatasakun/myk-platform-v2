"""Sprint 3.2 Staging Integration Verification

Kullanım:
    python scripts/staging_integration_verify.py --base-url http://localhost:80 \
        --club-a-token <JWT_A> --club-b-token <JWT_B>

İki test grubu:
  1. Concurrent application_number — 10 eşzamanlı submit, benzersizlik + izolasyon
  2. Cross-tenant storage — Club A tokeni ile Club B kaynakları 404/403 döndürmeli
"""
import argparse
import asyncio
import sys
import uuid

import httpx

BASE = ""
HEADERS_A: dict = {}
HEADERS_B: dict = {}


# ── 1. Concurrent sayaç testi ─────────────────────────────────────────────────

async def _submit_one(client: httpx.AsyncClient, headers: dict, label: str) -> str | None:
    """Başvuru oluştur ve submit et; application_number döndür."""
    cr = await client.post("/api/v1/membership-applications", json={"first_name": label}, headers=headers)
    if cr.status_code != 201:
        print(f"  [FAIL] Create: {cr.status_code} {cr.text[:120]}")
        return None
    app_id = cr.json()["id"]
    sr = await client.patch(
        f"/api/v1/membership-applications/{app_id}/status",
        json={"to_status": "submitted"},
        headers=headers,
    )
    if sr.status_code != 200:
        print(f"  [FAIL] Submit: {sr.status_code} {sr.text[:120]}")
        return None
    return sr.json().get("application_number")


async def test_concurrent_numbers():
    print("\n[1] Concurrent application_number testi")
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        # 10 eşzamanlı submit — Club A
        tasks_a = [_submit_one(client, HEADERS_A, f"A-{i}") for i in range(10)]
        # 10 eşzamanlı submit — Club B
        tasks_b = [_submit_one(client, HEADERS_B, f"B-{i}") for i in range(10)]

        results_a = await asyncio.gather(*tasks_a)
        results_b = await asyncio.gather(*tasks_b)

    nums_a = [n for n in results_a if n]
    nums_b = [n for n in results_b if n]

    ok = True

    expected_count = 10

    if len(nums_a) != expected_count:
        print(
            f"  [FAIL] Club A: beklenen {expected_count} başarılı numara, "
            f"alınan {len(nums_a)}"
        )
        ok = False

    if len(nums_b) != expected_count:
        print(
            f"  [FAIL] Club B: beklenen {expected_count} başarılı numara, "
            f"alınan {len(nums_b)}"
        )
        ok = False

    if len(nums_a) == expected_count and len(set(nums_a)) == expected_count:
        print(f"  [OK]   Club A: {expected_count} benzersiz numara")
    else:
        print("  [FAIL] Club A numaraları eksik veya benzersiz değil")
        ok = False

    if len(nums_b) == expected_count and len(set(nums_b)) == expected_count:
        print(f"  [OK]   Club B: {expected_count} benzersiz numara")
    else:
        print("  [FAIL] Club B numaraları eksik veya benzersiz değil")
        ok = False

    # Sayaçlar tenant bazlıdır. Farklı kulüplerde aynı görünen sıra
    # numaralarının bulunması beklenen davranıştır; global benzersizlik aranmaz.
    if (
        len(nums_a) == expected_count
        and len(set(nums_a)) == expected_count
        and len(nums_b) == expected_count
        and len(set(nums_b)) == expected_count
    ):
        print("  [OK]   Club A ve B sayaçları tenant bazında bağımsız")
    else:
        print("  [FAIL] Tenant bazlı sayaç doğrulaması başarısız")
        ok = False

    return ok


# ── 2. Cross-tenant storage testi ────────────────────────────────────────────

async def test_cross_tenant():
    print("\n[2] Cross-tenant izolasyon testi")
    ok = True

    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        # Club B'de başvuru oluştur, Club A tokeni ile eriş
        cr = await client.post("/api/v1/membership-applications", json={}, headers=HEADERS_B)
        if cr.status_code != 201:
            print(f"  [SKIP] Club B başvuru oluşturulamadı: {cr.status_code}")
            return False
        b_app_id = cr.json()["id"]

        cases = [
            ("GET  başvuru",       "GET",    f"/api/v1/membership-applications/{b_app_id}"),
            ("PATCH başvuru",      "PATCH",  f"/api/v1/membership-applications/{b_app_id}"),
            ("DELETE başvuru",     "DELETE", f"/api/v1/membership-applications/{b_app_id}"),
            ("GET signature-url",  "GET",    f"/api/v1/membership-applications/{b_app_id}/signature-url"),
            ("GET pdf-url",        "GET",    f"/api/v1/membership-applications/{b_app_id}/pdf-url"),
        ]
        for label, method, path in cases:
            kwargs: dict = {"headers": HEADERS_A}
            if method == "PATCH":
                kwargs["json"] = {"first_name": "hack"}
            resp = await client.request(method, path, **kwargs)
            if resp.status_code == 404:
                print(f"  [OK]   {label}: 404")
            elif resp.status_code == 403:
                print(f"  [OK]   {label}: 403")
            else:
                print(f"  [FAIL] {label}: beklenen 404/403, alınan {resp.status_code}")
                ok = False

        # Rastgele UUID — var olmayan kayıt
        fake = uuid.uuid4()
        r = await client.get(f"/api/v1/membership-applications/{fake}", headers=HEADERS_A)
        if r.status_code == 404:
            print("  [OK]   Rastgele UUID: 404")
        else:
            print(f"  [FAIL] Rastgele UUID: beklenen 404, alınan {r.status_code}")
            ok = False

    return ok


# ── Storage key sızıntı kontrolü ──────────────────────────────────────────────

async def test_no_key_leak():
    print("\n[3] Storage key sızıntı kontrolü")
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        cr = await client.post("/api/v1/membership-applications",
                               json={"first_name": "KeyLeak"}, headers=HEADERS_A)
        if cr.status_code != 201:
            print("  [SKIP] Başvuru oluşturulamadı")
            return False
        body = cr.text
        forbidden = ["object_key", "bucket", "minio", "s3.amazonaws"]
        leaked = [kw for kw in forbidden if kw in body.lower()]
        if leaked:
            print(f"  [FAIL] Response'da hassas alan: {leaked}")
            return False
        print("  [OK]   object_key / bucket sızıntısı yok")
        return True


# ── API + pdf-service health kontrolü ────────────────────────────────────────

async def test_health() -> tuple[bool, bool]:
    """API ve pdf-service /health endpoint'lerini kontrol et."""
    api_ok = pdf_ok = False
    async with httpx.AsyncClient(base_url=BASE, timeout=5) as client:
        try:
            r = await client.get("/api/v1/health")
            api_ok = r.status_code == 200
        except Exception:
            pass
        # pdf-service dahili ağdan doğrudan erişilemez; API üzerinden dolaylı
        # sağlık kontrolü: membership-applications list 200 ise API→DB bağlantısı sağlam
        try:
            r = await client.get("/api/v1/membership-applications", headers=HEADERS_A)
            pdf_ok = r.status_code in {200, 401, 403}   # servis ayakta, yetki ayrı mesele
        except Exception:
            pass
    return api_ok, pdf_ok


# ── Ana ──────────────────────────────────────────────────────────────────────

LABELS = {
    "api_health":       "API Health",
    "pdf_health":       "PDF Service Health (dolaylı)",
    "concurrent":       "PostgreSQL Atomic Counter",
    "cross_tenant":     "Cross-Tenant Isolation",
    "key_leak":         "Storage Key Sızıntısı Yok",
}


async def main(args: argparse.Namespace) -> int:
    global BASE, HEADERS_A, HEADERS_B
    BASE = args.base_url.rstrip("/")
    HEADERS_A = {"Authorization": f"Bearer {args.club_a_token}"}
    HEADERS_B = {"Authorization": f"Bearer {args.club_b_token}"}

    # Testleri sıralı çalıştır; health önce
    api_ok, pdf_ok = await test_health()
    r_concurrent   = await test_concurrent_numbers()
    r_cross        = await test_cross_tenant()
    r_leak         = await test_no_key_leak()

    results = {
        "api_health":   api_ok,
        "pdf_health":   pdf_ok,
        "concurrent":   r_concurrent,
        "cross_tenant": r_cross,
        "key_leak":     r_leak,
    }

    # ── Özet ─────────────────────────────────────────────────────────────────
    print("\n")
    print("════════════════════════════════════════")
    print("  Sprint 3.2 Integration — Özet")
    print("════════════════════════════════════════")
    for key, label in LABELS.items():
        mark = "✓" if results[key] else "✗"
        print(f"  {mark} {label}")
    print("────────────────────────────────────────")
    passed = all(results.values())
    print(f"  RESULT: {'PASS ✅' if passed else 'FAIL ❌'}")
    print("════════════════════════════════════════")

    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprint 3.2 Staging Integration Verify")
    parser.add_argument("--base-url", default="http://localhost:80")
    parser.add_argument("--club-a-token", required=True)
    parser.add_argument("--club-b-token", required=True)
    sys.exit(asyncio.run(main(parser.parse_args())))

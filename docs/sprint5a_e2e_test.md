# Sprint 5A — Uçtan Uca Üyelik Yaşam Döngüsü Testi

**Ortam:** Production — http://46.224.26.120:18081  
**Release:** v0.5.5 / Alembic: 0005  
**Durum:** ✅ PASS — 2026-08-08

---

## Hazırlık

### A. Admin token al

> **Not:** Login body'ye `club_slug` zorunludur.

```bash
TOKEN=$(curl -sX POST http://46.224.26.120:18081/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "akgun@akronis.com.tr",
    "password": "<PAROLA>",
    "club_slug": "mersin-yelken"
  }' | jq -r '.access_token')

echo "Token: ${TOKEN:0:40}..."
```

---

## Adım 1 — Halka açık başvuru gönder (auth yok)

```bash
curl -sX POST http://46.224.26.120:18081/api/v1/public/membership-applications \
  -H "Content-Type: application/json" \
  -d '{
    "club_slug": "mersin-yelken",
    "first_name": "Deniz",
    "last_name": "Test",
    "email": "deniz.test@ornek.com",
    "phone": "05321234567",
    "birth_date": "2010-06-15",
    "gender": "erkek",
    "national_id": "12312312312",
    "address": "Mersin Test Sokak No:1",
    "blood_type": "A+",
    "emergency_contact_name": "Veli Test",
    "emergency_contact_phone": "05329876543",
    "consent_accepted": true
  }' | jq '{id, application_number, status}'
```

**Beklenen:**
```json
{
  "id": "<UUID>",
  "application_number": "MYK-2026-000001",
  "status": "submitted"
}
```

> **Not:** Başvuru numarası formatı `MYK-2026-NNNNNN` (4 basamaklı değil, 6 basamaklı ve 4 haneli yıl).

```bash
APP_ID="<yukarıdan gelen id>"
```

---

## Adım 2 — Dashboard sayacı kontrol et

```bash
curl -s http://46.224.26.120:18081/api/v1/dashboard/stats \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '{bekleyen_basvuru, aktif_uye, toplam_kisi}'
```

**Beklenen:** `bekleyen_basvuru` ≥ 1

---

## Adım 3 — Başvuruyu listele

> **Not:** Doğru endpoint `/api/v1/membership-applications` (tire ile, `memberships/` öneki yok).

```bash
curl -s "http://46.224.26.120:18081/api/v1/membership-applications?status=submitted" \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '.items[] | {id, application_number, first_name, last_name, status}'
```

---

## Adım 4 — Başvuruyu onayla

> **Not:** HTTP metodu `PATCH`.

```bash
curl -sX PATCH \
  "http://46.224.26.120:18081/api/v1/membership-applications/${APP_ID}/status" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"to_status": "approved"}' \
  | jq '{id, status, approved_at, person_id}'
```

**Beklenen:**
```json
{
  "status": "approved",
  "approved_at": "2026-...",
  "person_id": "<UUID>"
}
```

```bash
PERSON_ID="<yukarıdan gelen person_id>"
```

---

## Adım 5 — Person ve üye numarası doğrula

> **Not:** `member_number` API yanıtında görünmeyebilir; doğrulama DB üzerinden yapılmalıdır.

**API üzerinden:**
```bash
curl -s "http://46.224.26.120:18081/api/v1/persons/${PERSON_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '{id, first_name, last_name, national_id, is_active, roles}'
```

**DB üzerinden (member_number için):**
```bash
# Sunucuda:
docker compose --env-file /etc/myk/production.env \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T db psql -U myk_user myk_platform_prod -c \
  "SELECT member_number, must_change_password FROM persons WHERE id = '${PERSON_ID}';"
```

**Beklenen:**
```
 member_number | must_change_password
---------------+---------------------
 MYK-26-0001   | f
```

> **Not:** `must_change_password` canlı sistemde `false` dönüyor. Birinci girişte zorunlu şifre değiştirme akışı (force-change flag'i) iş kuralı olarak Sprint 5B veya sonrasında ayrıca değerlendirilmelidir.

**Kontrol listesi:**
- [ ] `roles` içinde `"uye"` var
- [ ] `is_active: true`
- [ ] `member_number` format: `MYK-26-NNNN` (DB'de)
- [ ] Alanlar başvurudan kayıpsız aktarılmış

---

## Adım 6 — Kullanıcı hesabı doğrula

```bash
curl -s "http://46.224.26.120:18081/api/v1/persons/${PERSON_ID}/user" \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '{email, role, is_active, person_id}'
```

**Beklenen:**
```json
{
  "email": "deniz.test@ornek.com",
  "role": "uye",
  "is_active": true,
  "person_id": "<PERSON_ID ile eşleşmeli>"
}
```

---

## Adım 7 — Dashboard güncellendi mi?

```bash
curl -s http://46.224.26.120:18081/api/v1/dashboard/stats \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '{bekleyen_basvuru, aktif_uye, toplam_kisi}'
```

**Beklenen:** `bekleyen_basvuru` -1, `aktif_uye` +1, `toplam_kisi` +1

---

## Adım 8 — İdempotency testi (aynı TC ile ikinci başvuru)

```bash
# Aynı national_id ile ikinci başvuru
APP_ID2=$(curl -sX POST http://46.224.26.120:18081/api/v1/public/membership-applications \
  -H "Content-Type: application/json" \
  -d '{
    "club_slug": "mersin-yelken",
    "first_name": "Deniz",
    "last_name": "Test",
    "email": "deniz.test@ornek.com",
    "phone": "05321234567",
    "national_id": "12312312312",
    "consent_accepted": true
  }' | jq -r '.id')

# İkinci başvuruyu onayla
curl -sX PATCH \
  "http://46.224.26.120:18081/api/v1/membership-applications/${APP_ID2}/status" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"to_status": "approved"}' \
  | jq '{status, person_id}'
```

**Beklenen:** `person_id` ilk başvuruyla **aynı UUID**.

**DB doğrulaması:**
```sql
SELECT COUNT(*) FROM persons
WHERE national_id = '12312312312' AND club_id = '<CLUB_UUID>';
-- Beklenen: 1
```

---

## Adım 9 — Terminal durum engeli testi

```bash
# Zaten approved olan başvuruyu tekrar approve etmeye çalış
curl -sX PATCH \
  "http://46.224.26.120:18081/api/v1/membership-applications/${APP_ID}/status" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"to_status": "approved"}' \
  | jq '{detail}'
```

**Beklenen:** 422 veya 400 — `approved → approved` geçişi engellenmiş.

---

## Adım 10 — Şifre sıfırlama request (opsiyonel)

```bash
curl -sX POST http://46.224.26.120:18081/api/v1/auth/reset-password/request \
  -H "Content-Type: application/json" \
  -d '{
    "club_slug": "mersin-yelken",
    "email": "deniz.test@ornek.com"
  }'
# Beklenen: HTTP 204
```

---

## Özet — Production E2E Sonucu (2026-08-08)

| # | Test | Beklenen | Sonuç |
|---|------|----------|-------|
| 1 | Public başvuru (auth yok) | 201, MYK-2026-NNNNNN | ✅ |
| 2 | Dashboard bekleyen_basvuru | +1 | ✅ |
| 3 | Başvuru listede görünüyor | ✓ | ✅ |
| 4 | PATCH onaylama → person_id | approved + person_id | ✅ |
| 5 | Person + üye numarası (DB) | MYK-26-0001, role=uye | ✅ |
| 6 | User hesabı oluştu | email + role + person_id | ✅ |
| 7 | Dashboard güncellendi | bekleyen-1, aktif_uye+1 | ✅ |
| 8 | İdempotency (aynı TC) | Tek Person, aynı person_id | ✅ |
| 9 | approved→approved engeli | 4xx hatası | ✅ |

**Sonuç: PASS 🎉**

---

## Açık Maddeler (Sprint 5B+)

- `member_number` API yanıtına eklenmeli (şu an yalnızca DB'de görünüyor)
- `must_change_password` first-login force-change akışı iş kuralı olarak tanımlanmalı
- Veli-sporcu ilişkilendirme uygulanmadı
- E-posta SMTP production yapılandırması (şu an log-mode)

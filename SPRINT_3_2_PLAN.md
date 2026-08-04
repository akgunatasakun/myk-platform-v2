# SPRINT 3.2 — Avatar, PDF Üyelik Formu ve İmza
**Versiyon:** v0.4.0-dev  
**Baz sürüm:** v0.3.1 (Sprint 3.1 tamamlandı, staging canlı)  
**Oluşturma tarihi:** 2026-08-04  
**Durum:** ONAYLANDI (v1.0)

---

## 1. Sprint Amacı

Sprint 3.1'de kişi yönetimi (CRUD, RBAC, tenant izolasyonu) tamamlandı.  
Sprint 3.2'nin amacı bu kişilere **medya varlığı** ve **belge kimliği** kazandırmaktır:

- Kişi fotoğrafı (avatar) yükleme, kırpma ve private object storage'da saklama
- Kişi detay ekranının zenginleştirilmesi
- Dinamik branş tablosu (`sports_branches`) ve üyelik başvuru veri modeli
- WeasyPrint tabanlı ayrı PDF servisi ile sunucu tarafı üyelik formu üretimi
- Canvas imzası alınması ve PDF'e işlenmesi
- QR kodlu dijital üye kartı

---

## 2. Kapsam Dışı (Bu Sprint)

| Konu | Açıklama |
|---|---|
| E-İmza / NES | Nitelikli elektronik sertifika — ileriki faz |
| Redis job queue | Senkron HTTP yeterli; yük artarsa Sprint 3.3'te eklenir |
| Thumbnail async worker | İlk sürüm sync resize; Sprint 4'te async worker'a taşınabilir |
| Aidat/ödeme | Sprint 3.3 |
| Mobil uygulama | Sprint 5 |
| Public avatar URL | Avatar her zaman private; pre-signed URL ile servis edilir |
| Production S3 geçişi | Staging MinIO; production yalnızca `.env` değişikliği — ayrı task |

---

## 3. Kapalı Açık Sorular

| # | Soru | Karar | Gerekçe |
|---|---|---|---|
| OQ-01 | MinIO için ayrı sunucu mu? | Aynı VM (staging); production'da Hetzner Object Storage veya S3 | Mevcut yük için yeterli; `.env` ile geçiş yapılır |
| OQ-02 | Branşlar sabit enum mu? | **Hayır — `sports_branches` tablosu** | SUP, Para Yelken vb. ileride migration gerektirmeden eklenebilmeli |
| OQ-03 | Üye kartı arka yüz | Kulüp iletişim bilgileri + "Bu kart kulüp mülkiyetidir." + acil durum telefonu, adres, web sitesi | QR kod doğrulama URL'si açmalı (yalnızca üye no değil) |
| OQ-04 | Başvuru onaylayan rol | `kulup_yonetici` + `sistem_yoneticisi` | Antrenör/ofis başvuru oluşturabilir, onaylayamaz |

---

## 4. Mimari Karar Kayıtları (ADR)

### ADR-S32-001 — ObjectStorageService Abstraction

**Karar:** Uygulama doğrudan MinIO SDK'sını çağırmaz. Tüm storage işlemleri `app/services/storage.py` içindeki `ObjectStorageService` üzerinden yürütülür.

**Gerekçe:** `.env` değişkenleri değiştirilerek MinIO → AWS S3 → Hetzner Object Storage geçişi yapılabilmeli; uygulama kodu değişmemeli. `exists()` ve `copy()` Sprint 4 belge versiyonlama için şimdiden eklenir.

**Arayüz:**
```python
class ObjectStorageService:
    async def upload(self, key: str, data: bytes, content_type: str) -> str
    async def delete(self, key: str) -> None
    async def exists(self, key: str) -> bool
    async def copy(self, src_key: str, dst_key: str) -> None
    async def presigned_url(self, key: str, expires: int) -> str
    async def presigned_url_batch(self, keys: list[str], expires: int) -> dict[str, str]
```

**Env değişkenleri:**
```
STORAGE_ENDPOINT=http://minio:9000
STORAGE_ACCESS_KEY=...
STORAGE_SECRET_KEY=...
STORAGE_BUCKET=myk-person-media
STORAGE_REGION=us-east-1
```

---

### ADR-S32-002 — Veritabanında URL Değil `avatar_object_key`

**Karar:** `persons.avatar_url` kolonu kaldırılır, yerine `avatar_object_key` eklenir.

**Gerekçe:** Storage sağlayıcısı veya domain değiştiğinde veritabanı güncellemesi gerekmez. Pre-signed URL çalışma zamanında üretilir.

**Object key formatı — aktif avatar:**
```
clubs/{club_id}/persons/{person_id}/avatar/current.webp
```

**Arşiv (geri alma desteği):**
```
clubs/{club_id}/persons/{person_id}/avatar/archive/{YYYYMMDD_HHMMSS}.webp
```

Yeni avatar yüklendiğinde eski `current.webp`, `archive/` altına `copy()` ile taşınır, ardından yeni görsel `current.webp` olarak yazılır. Böylece yanlış yükleme durumunda arşivden geri dönülebilir (bu sprint'te UI yok; arka kapı olarak hazır kalır).

---

### ADR-S32-003 — Pre-Signed URL Süresi

| Kullanım | Süre |
|---|---|
| Kişi listesi / detay (UI görüntüleme) | 3600 saniye (1 saat) |
| PDF indirme | 900 saniye (15 dakika) |
| İmza dosyası indirme (audit) | 900 saniye (15 dakika) |

**PersonOut'a eklenen alanlar:**
```python
avatar_url: Optional[str]   # pre-signed URL, 3600s; avatar yoksa None
has_avatar: bool             # frontend URL kontrolü yapmak zorunda kalmaz
```

**Kişi listesi N+1 önlemi:** `GET /persons` yanıtı tüm kişilerin key'lerini tek `presigned_url_batch()` çağrısıyla işler.

---

### ADR-S32-004 — PDF Üretimi Ayrı Container'da

**Karar:** WeasyPrint, API image'ına dahil edilmez. `pdf-service` adında ayrı bir FastAPI mikro servisi olarak çalışır.

**Gerekçe:** WeasyPrint + Pango/Cairo bağımlılıkları ~200 MB'tır. API container'ı şişirilmemeli.

**İletişim:** API → `http://pdf-service:8001/generate` (dahili Docker ağı, dışarıya port publish edilmez)

**İlk sürüm:** Senkron HTTP çağrısı. Zaman aşımı: 30 saniye. Hata durumunda API 503 döner.

**`/health` endpoint:** API startup sırasında ve her istek öncesinde pdf-service hazırlığı kontrol edilir. pdf-service yanıt vermezse `503 PDF service unavailable` döner; diğer API işlemleri etkilenmez.

---

### ADR-S32-005 — Canvas İmzası Multipart/Form-Data

**Karar:** İmza görüntüsü `application/json` içinde base64 olarak gönderilmez. `multipart/form-data` ile `image/png` dosyası olarak gönderilir.

**Gerekçe:** Base64 payload büyüklüğü ve injection riski. Mevcut avatar upload mekanizmasıyla tutarlılık.

---

### ADR-S32-006 — Canvas İmzası "Islak İmza Görseli" Sınıflandırması

**Karar:** Canvas üzerinde alınan çizim, hukuken "güvenli elektronik imza" sayılmaz. İlk sürümde bu alan **kullanıcı onay görseli** olarak tanımlanır ve audit kaydına bu şekilde yazılır.

**Gerekçe:** 5070 sayılı Elektronik İmza Kanunu kapsamındaki nitelikli elektronik imza için sertifika altyapısı gereklidir — bu, ayrı bir ileriki fazdır.

---

### ADR-S32-007 — Audit Entegrasyonu + İmza SHA-256

**Karar:** Tüm olaylar mevcut `log_action()` mekanizmasına bağlanır. PDF SHA-256'ya ek olarak `signature_sha256` da audit kaydına yazılır — ileride hukuki denetim için.

**Yeni action kodları:**
```
avatar_uploaded, avatar_deleted,
membership_pdf_generated, membership_signed,
member_card_downloaded
```

**`membership_applications` tablosuna eklenen alan:**
```sql
signature_sha256 VARCHAR(64)   -- ham imza görselinin SHA-256'sı
```

---

### ADR-S32-008 — Branşlar Dinamik (`sports_branches` Tablosu)

**Karar:** Branşlar sabit enum olarak tanımlanmaz; `sports_branches` tablosundan gelir.

**Gerekçe:** SUP, Para Yelken vb. branşlar migration gerektirmeden eklenebilmeli.

**Başlangıç veri (seed):**
Yelken, Optimist, ILCA, 420, 470, Wingfoil, Windsurf, Kitesurf, Kano

---

## 5. Veritabanı Değişiklikleri

### Migration 0003 — Avatar, Branşlar ve Üyelik Başvurusu

**Dosya:** `backend/migrations/versions/0003_avatar_membership.py`

```sql
-- ── 1. persons: avatar_url → avatar_object_key ────────────────────────────
ALTER TABLE persons DROP COLUMN avatar_url;
ALTER TABLE persons ADD COLUMN avatar_object_key VARCHAR(500);

-- ── 2. sports_branches (dinamik branş tablosu) ────────────────────────────
CREATE TABLE sports_branches (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id     UUID NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_sports_branches_club_id ON sports_branches(club_id);
CREATE UNIQUE INDEX uq_sports_branches_name ON sports_branches(club_id, name);

-- ── 3. membership_applications ────────────────────────────────────────────
CREATE TABLE membership_applications (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id               UUID NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    person_id             UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    applicant_name        VARCHAR(200) NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'draft',
      -- draft | submitted | signed | approved | rejected
    form_data             JSONB,
    pdf_object_key        VARCHAR(500),
    pdf_sha256            VARCHAR(64),
    signature_object_key  VARCHAR(500),
    signature_sha256      VARCHAR(64),
    signed_at             TIMESTAMPTZ,
    signed_by_user_id     UUID,
    approved_by_user_id   UUID,
    approved_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_membership_applications_club_id   ON membership_applications(club_id);
CREATE INDEX ix_membership_applications_person_id ON membership_applications(person_id);
CREATE INDEX ix_membership_applications_status    ON membership_applications(club_id, status);
```

**GRANT (PostgreSQL only):**
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON sports_branches TO myk_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON membership_applications TO myk_app;
```

**Downgrade:** `avatar_object_key` kaldır → `avatar_url` geri ekle, `membership_applications` drop, `sports_branches` drop.

---

## 6. Object Storage Dizin Yapısı

```
myk-person-media/                              ← tek bucket, private
  clubs/
    {club_id}/
      persons/
        {person_id}/
          avatar/
            current.webp                       ← aktif avatar
            archive/
              {YYYYMMDD_HHMMSS}.webp           ← önceki avatarlar
          documents/
            membership/
              {application_id}/
                form_{uuid}.pdf                ← imzasız form
                signed_{uuid}.pdf              ← imzalı final
                signature_{uuid}.png           ← ham imza görseli
```

**Tenant izolasyonu:** Her nesne yolunun ilk segmenti `clubs/{club_id}/`. Backend her işlemde JWT'den alınan `club_id`'yi key oluşturmak için kullanır; kullanıcı key'i doğrudan kontrol edemez.

---

## 7. Backend Endpoint Sözleşmeleri

### 7.1 Avatar

| Method | Path | RBAC | Açıklama |
|---|---|---|---|
| POST | `/api/v1/persons/{person_id}/avatar` | `kisi:write` | Avatar yükle (multipart/form-data, `file` alanı) |
| DELETE | `/api/v1/persons/{person_id}/avatar` | `kisi:write` | Avatar sil |

**POST avatar iş akışı:**
1. MIME doğrulama: `python-magic` ile magic bytes kontrolü (yalnızca `image/jpeg`, `image/png`, `image/webp`)
2. Boyut limiti: 10 MB
3. Pillow ile yeniden boyutlandır: 400×400 px, WebP, kalite 85
4. Eski `current.webp` varsa → `archive/{YYYYMMDD_HHMMSS}.webp` olarak `copy()`, sonra `delete()`
5. Yeni görsel → `clubs/{club_id}/persons/{person_id}/avatar/current.webp` olarak `upload()`
6. `persons.avatar_object_key` güncelle
7. `log_action("avatar_uploaded", after={"avatar_object_key": ..., "file_size_bytes": ...})`
8. `PersonOut` döndür (`has_avatar=True`, `avatar_url=pre-signed URL`)

**List endpoint N+1 önlemi:**
```python
keys = [p.avatar_object_key for p in persons if p.avatar_object_key]
url_map = await storage.presigned_url_batch(keys, expires=3600)
for item in items:
    item.avatar_url = url_map.get(item.avatar_object_key)
    item.has_avatar = item.avatar_object_key is not None
```

---

### 7.2 Branşlar

| Method | Path | RBAC | Açıklama |
|---|---|---|---|
| GET | `/api/v1/branches` | `kisi:read` | Kulübün aktif branşlarını listele |
| POST | `/api/v1/branches` | `kisi:write` | Branş ekle (yönetici) |
| PATCH | `/api/v1/branches/{id}` | `kisi:write` | Branş güncelle / deaktif et |

---

### 7.3 Üyelik Başvurusu

| Method | Path | RBAC | Açıklama |
|---|---|---|---|
| POST | `/api/v1/memberships` | `kisi:write` | Başvuru oluştur (draft) |
| GET | `/api/v1/memberships/{id}` | `kisi:read` | Başvuru detayı |
| POST | `/api/v1/memberships/{id}/generate-pdf` | `kisi:write` | PDF üret (pdf-service) |
| GET | `/api/v1/memberships/{id}/pdf-url` | `kisi:read` | İmzasız PDF pre-signed URL (15 dk) |
| POST | `/api/v1/memberships/{id}/signature` | `kisi:write` | İmza yükle (multipart/form-data) |
| GET | `/api/v1/memberships/{id}/signed-pdf-url` | `kisi:read` | İmzalı PDF pre-signed URL (15 dk) |
| PATCH | `/api/v1/memberships/{id}/status` | `kisi:approve` | Onayla / reddet (yönetici) |

**Durum geçiş kuralı:**
```
draft → submitted  (kisi:write)
submitted → signed (kisi:write — imza yüklendikten sonra otomatik)
signed → approved  (kisi:approve — kulup_yonetici veya sistem_yoneticisi)
signed → rejected  (kisi:approve)
approved → (terminal)
rejected → draft   (kisi:write — yeniden başvuru)
```

---

### 7.4 Üye Kartı

| Method | Path | RBAC | Açıklama |
|---|---|---|---|
| GET | `/api/v1/persons/{person_id}/member-card` | `kisi:read` | QR kodlu üye kartı PDF pre-signed URL (15 dk) |

**QR kod içeriği:** `https://{domain}/verify/{person_id}` — üye numarasını değil doğrulama URL'sini açar.

**Üye kartı arka yüz içeriği:** Kulüp adı, adres, acil durum telefonu, web sitesi, "Bu kart kulüp mülkiyetidir." ibaresi.

---

## 8. PDF Service (`pdf-service`)

### Dizin yapısı (yeni)
```
pdf-service/
  Dockerfile
  requirements.txt           # fastapi, uvicorn, weasyprint, qrcode[pil], jinja2, pillow
  main.py
  templates/
    membership_form.html
    member_card_front.html
    member_card_back.html
  static/
    logo.png                  ← frontend/public/logo.png'dan kopyalanacak
    style.css
```

### API (dahili, dışarıya açık değil)

```
GET  http://pdf-service:8001/health
→ 200 {"status": "ok"}

POST http://pdf-service:8001/generate
Content-Type: application/json
{
  "template": "membership_form",    // membership_form | member_card
  "data": { ... },
  "signature_png_b64": "..."        // opsiyonel — imzalı form için
}
→ 200 OK
Content-Type: application/pdf
Body: <binary PDF>
```

**Hata durumları:**
- `422` — geçersiz template adı
- `500` — WeasyPrint render hatası (log kaydedilir, API'ye `503` döner)

### Dockerfile (pdf-service)
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
    libgdk-pixbuf2.0-0 libffi-dev \
    fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### docker-compose.yml eklentisi
```yaml
  pdf-service:
    build:
      context: ./pdf-service
      dockerfile: Dockerfile
    restart: unless-stopped
    networks:
      - backend
    # port publish YOK — yalnızca dahili ağ

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${STORAGE_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${STORAGE_SECRET_KEY}
    volumes:
      - minio_data:/data
    networks:
      - backend
    # port publish YOK production'da; staging debug için 9000/9001 açılabilir

volumes:
  minio_data:
```

---

## 9. Frontend Ekranlar ve Bileşenler

### 9.1 Kişi Detay Ekranı — Geliştirme
- Avatar gösterimi (`has_avatar` kontrolü; yoksa baş harfleri placeholder)
- Avatar yükleme butonu → `AvatarCropModal`
- Üyelik başvuruları sekmesi

### 9.2 AvatarCropModal (yeni bileşen)
```
1. input[type=file] accept="image/*"
2. Seçilen görüntü canvas'ta kare kırpma arayüzü (react-easy-crop veya vanilya)
3. "Kaydet" → canvas.toBlob("image/png") → FormData → POST /avatar
4. Başarıda PersonDetailPage yenilenir, yeni avatar_url ile img güncellenir
```
*Kırpma istemci tarafında; sunucu MIME + boyut doğrulama ve WebP dönüşümü yapar.*

### 9.3 MembershipFormPage (yeni sayfa — `/persons/{id}/membership/apply`)
```
- Kişi bilgileri otomatik doldurulur (read-only)
- Branş seçimi: GET /branches'tan dinamik yüklenir
- Ek alanlar: iletişim tercihleri, acil durum bilgisi
- "PDF Önizleme" → generate-pdf → PDF viewer (iframe)
- "İmzala" → SignatureModal
```

### 9.4 SignatureModal (yeni bileşen)
```
- Canvas imza çizim alanı
- "Temizle" butonu
- "Onayla ve Gönder" (canvas boşken disabled):
    canvas.toBlob("image/png") → FormData → POST /signature
```

### 9.5 MemberCardPage (yeni sayfa — `/persons/{id}/member-card`)
```
- Üye bilgileri + QR kod önizlemesi
- "PDF İndir" → member-card pre-signed URL (yeni sekmede açılır)
```

---

## 10. Güvenlik Kontrolleri

| Kontrol | Uygulama yeri |
|---|---|
| MIME doğrulama (magic bytes) | Backend: `python-magic` — header'a güvenilmez |
| Boyut limiti | Backend: 10 MB (avatar), 5 MB (imza) |
| Dosya uzantısı | Backend: .jpg, .jpeg, .png, .webp |
| Object key manipülasyonu | Key her zaman `clubs/{jwt_club_id}/...` — kullanıcıdan gelmez |
| Tenant izolasyonu | `club_id` JWT'den alınır |
| Pre-signed URL süresi | Avatar: 3600s, PDF/imza: 900s |
| PDF boyutu kontrolü | pdf-service: 50 MB aşarsa 413 |
| İmza görseli boyutu | 5 MB limit |
| Durum geçiş yetkilendirmesi | `approved`/`rejected` → yalnızca `kisi:approve` rolü |

---

## 11. Audit Olayları

| action | resource_type | after alanları |
|---|---|---|
| `avatar_uploaded` | `person` | `avatar_object_key`, `file_size_bytes` |
| `avatar_deleted` | `person` | `previous_key` |
| `membership_pdf_generated` | `membership_application` | `pdf_object_key`, `pdf_sha256` |
| `membership_signed` | `membership_application` | `signature_object_key`, `signature_sha256`, `signed_at` |
| `membership_approved` | `membership_application` | `approved_by`, `approved_at` |
| `membership_rejected` | `membership_application` | `rejected_by`, `reason` |
| `member_card_downloaded` | `person` | `downloaded_at` |

---

## 12. Test Matrisi

### Backend (pytest + mock storage)

| # | Test | Açıklama |
|---|---|---|
| AV-01 | Avatar upload happy path | JPEG yükle → WebP kaydedildi, `has_avatar=True`, URL döndü |
| AV-02 | MIME reddi | `text/plain` → 422 |
| AV-03 | Boyut aşımı | 11 MB → 413 |
| AV-04 | Arşivleme | İkinci yüklemede eski key `archive/` altına taşındı |
| AV-05 | Cross-tenant engeli | B kulübü kişisine A token → 404 |
| AV-06 | N+1 yok | 10 kişi listesi → tek `presigned_url_batch()` çağrısı |
| BR-01 | Branş listeleme | Kulübün aktif branşları döndü |
| BR-02 | Branş ekleme | Yeni branş seed listesine eklendi |
| BR-03 | Cross-tenant branş | Başka kulüp branşına erişim → 404 |
| MB-01 | Başvuru oluşturma | `draft` status, club_id eşleşiyor |
| MB-02 | PDF üretimi | pdf-service mock, `pdf_object_key` + `pdf_sha256` kaydedildi |
| MB-03 | İmza yükleme | multipart PNG, `signed` status, `signature_sha256` audit'e yazıldı |
| MB-04 | PDF URL | 900s pre-signed URL döndü |
| MB-05 | Cross-tenant başvuru | Başka kulübün başvurusu → 404 |
| MB-06 | Durum geçiş yetkisi | `kisi:write` ile `approved` → 403 |
| MB-07 | Onaylama | `kisi:approve` ile `approved` → 200 |
| QR-01 | Üye kartı URL | 900s pre-signed URL döndü |

### Frontend (vitest)

| # | Test |
|---|---|
| FE-01 | AvatarCropModal — dosya seçimi canvas render'lar |
| FE-02 | AvatarCropModal — "Kaydet" multipart FormData gönderir |
| FE-03 | SignatureModal — canvas boşken "Onayla" disabled |
| FE-04 | PersonDetailPage — `has_avatar=false` → baş harfi placeholder |
| FE-05 | PersonDetailPage — `has_avatar=true` → img src=avatar_url |

### Entegrasyon (staging)

| # | Test |
|---|---|
| INT-01 | Avatar yükle → GET /persons/{id} → `has_avatar=true`, `avatar_url` 200 döner |
| INT-02 | Başvuru oluştur → PDF üret → imzala → İmzalı PDF URL 200 |
| INT-03 | Üye kartı PDF indir → 200, Content-Type: application/pdf |
| INT-04 | pdf-service /health → 200 |
| INT-05 | MinIO bucket erişimi → PUT/GET/DELETE başarılı |

---

## 13. Deployment ve Rollback

### Yeni servisler
- `pdf-service` container
- `minio` container (staging)

### MinIO ilk kurulum (staging, tek seferlik)
```bash
docker compose exec minio mc alias set local http://minio:9000 $STORAGE_ACCESS_KEY $STORAGE_SECRET_KEY
docker compose exec minio mc mb local/myk-person-media
docker compose exec minio mc policy set private local/myk-person-media
```

### Deployment sırası
```
1. MinIO + pdf-service container'larını başlat
2. MinIO bucket oluştur (ilk kez)
3. pdf-service /health → 200 doğrula
4. API image yeniden build (0003 migration + yeni endpoint'ler)
5. Alembic upgrade head (myk_user credentials, mevcut yöntem)
6. Sports branches seed verisi yükle
7. Frontend build (yeni sayfalar)
8. docker compose up -d --force-recreate
```

### Rollback
```
1. docker compose up -d --force-recreate api  (önceki image tag)
2. Alembic downgrade -1
3. pdf-service ve minio stop (bağımlılık yok — api çalışmaya devam eder)
4. MinIO data volume silinmez (veri kaybı riski)
```

---

## 14. Definition of Done

Sprint 3.2 tamamlanmış sayılır:

- [ ] Migration 0003 staging'de çalışıyor (upgrade + downgrade doğrulandı)
- [ ] MinIO staging'de ayakta, bucket oluşturuldu, private policy aktif
- [ ] `sports_branches` seed verisi yüklendi (9 branş)
- [ ] Avatar yükleme: WebP, arşivleme, `has_avatar`, pre-signed URL, N+1 yok
- [ ] Cross-tenant avatar erişimi 404 döndürüyor
- [ ] PDF üretimi pdf-service üzerinden, `pdf_sha256` audit kaydında
- [ ] Canvas imzası multipart, `signature_sha256` audit kaydında
- [ ] QR kod doğrulama URL'sini açıyor
- [ ] Üye kartı arka yüzünde kulüp bilgileri mevcut
- [ ] `kulup_yonetici` / `sistem_yoneticisi` dışındaki roller `approved` yapamıyor
- [ ] Tüm backend testleri yeşil (53 mevcut + 17 yeni = **70 test**)
- [ ] Frontend TSC=0, lint=0, build başarılı
- [ ] Entegrasyon testleri INT-01/02/03/04/05 geçti
- [ ] Sprint 3.2 verify script FAIL=0

---

## 15. Forward Compatibility (Sprint 4 Hazırlığı)

Sprint 3.2'de alınan mimari kararlar Sprint 4 kapsamını göz önünde bulundurarak şekillendirildi:

| Sprint 3.2 kararı | Sprint 4'e sağladığı hazırlık |
|---|---|
| `ObjectStorageService.exists()` + `copy()` | Belge versiyonlama altyapısı |
| `avatar/archive/` yapısı | Genel medya versiyonlama deseni |
| `sports_branches` dinamik tablo | Para Yelken, SUP vb. migration gerektirmeden eklenir |
| `signature_sha256` audit kaydı | Hukuki denetim logu — Sağlık raporu, Veli onay belgesi |
| PDF ayrı container | SMS/Mail bildirim servisi de aynı şekilde ayrı container olacak |
| QR doğrulama URL formatı | Kart doğrulama ekranı (`/verify/{person_id}`) Sprint 4'te UI kazanır |
| `kisi:approve` RBAC kodu | Aidat onayı, lisans onayı için aynı pattern genişletilebilir |

**Sprint 4 öngörülen kapsam:**
- Aidat sistemi + online ödeme
- Lisans takibi
- Sağlık raporu ve veli onay belgeleri
- SMS / Mail bildirimleri (ayrı notification-service container)
- Kart doğrulama ekranı (`/verify/{person_id}`)
- Tekne ve ekipman zimmet modülü

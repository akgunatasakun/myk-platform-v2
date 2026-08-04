# Sprint 3.1 — Temel Kişi ve Üyelik Mimarisi (REV2)

**Durum:** BEKLEME — Sprint 3.0-A PASS olduktan sonra başlanacak  
**Önkoşul:** `s3_0a_verify.sh` → exit 0 veya exit 2  
**Revizyon:** REV2 — bağımsız inceleme bulgularına göre 15 mimari sorun giderildi

---

## REV1 → REV2 Değişiklikleri

| # | REV1 Sorunu | REV2 Düzeltmesi |
|---|---|---|
| 1 | "12 tablo + 2 junction" — eksik sayım | 18 tablo (aşağıda tam liste) |
| 2 | `tc_identity` Sprint 3.2'ye ertelendi | Sprint 3.1'de: AES-256 (pgcrypto) + HMAC-SHA256 hash — ikisi birlikte |
| 3 | `users` tablosunun `persons` ile bağlantısı yok | `users.person_id UUID FK → persons.id NULLABLE` eklendi |
| 4 | `person_roles` iş rollerini auth rolleriyle karıştırıyor | `person_capacities` ayrı tablo; `person_roles` → auth sistemiyle birleşik; ikisi ayrıldı |
| 5 | Antrenör–sporcu ataması: `coaches` tablosunda yer almıyor | `coach_athlete_assignments` junction tablosu eklendi |
| 6 | `membership_type` değerleri gerçekçi değil | 'aktif_sporcu','lisanssiz_sporcu','veli_uye','onursal','personel','misafir','kurumsal' |
| 7 | `contact_information.contact_type` içinde 'adres' var — `addresses` tablosu ayrı | CHECK kısıtından 'adres' çıkarıldı |
| 8 | `boat_class`, `specializations` serbest metin — normalize edilmedi | `disciplines` ve `boat_classes` referans tabloları eklendi |
| 9 | `athletes.license_no` + `coaches.license_no` — tek lisans per kişi | `person_licenses` ayrı tablo: bir kişi birden fazla lisans taşıyabilir |
| 10 | Composite FK yok — tenant izolasyonu sadece uygulama katmanında | `(club_id, id)` composite PK pattern; FK'lar tenant'ı taşıyan FK'ya referans |
| 11 | `consents` tek satır güncelleniyor — revoke mutable | `consent_definitions` + `consent_events` immutable event model |
| 12 | `person_documents` yeterince detaylı değil | `hash_sha256`, `storage_provider`, `is_deleted` eklendi |
| 13 | Partial unique index yok — soft delete sonrası sorun | `WHERE is_deleted = FALSE` partial unique index'ler |
| 14 | Tablo başına dokümantasyon yok | Her tabloya açıklama ve güvenlik notu eklendi |
| 15 | Çıktı seti eksik: plan + ER diyagramı + migration + test planı | ER diyagramı (text), migration adımları, test matrisi tam |

---

## Tablo Listesi (18 Tablo)

```
Çekirdek:
  persons                    — merkezi kişi kaydı (TC encrypted + HMAC)
  users                      — mevcut auth tablosu + person_id FK eklendi

İş Rolleri / Kapasite:
  person_capacities          — iş rolleri (antrenor, muhasebe, idareci...)
  coach_athlete_assignments  — antrenör–sporcu atamaları

Üyelik / Profil:
  memberships                — üyelik kaydı (tip, durum, dönem)
  athletes                   — sporcu profili (lisanssız alan, ELO vb.)
  coaches                    — antrenör profili (seviye, uzmanlık)
  guardians                  — veli–sporcu ilişkisi

Lisans:
  person_licenses            — kişi başına N lisans (sporcu + antrenör)

İletişim:
  contact_information        — telefon, e-posta, sosyal medya
  addresses                  — adresler (ayrı normalize tablo)
  emergency_contacts         — acil durum kişileri

KVKK / Onay:
  consent_definitions        — onay şablonları (hangi hak, hangi metin)
  consent_events             — immutable olay kaydı (verildi/reddedildi/geri_alindi)

Belgeler:
  person_documents           — dosya metadata + hash + storage ref

Referans Tabloları:
  disciplines                — branş listesi (yelken, windsurf, hobi...)
  boat_classes               — tekne sınıfları (Optimist, Laser, 420...)
```

---

## Tablo Şemaları

### persons
> Tüm iş modüllerinin köküdür. TC kimlik verisini AES-256 ile şifreler,  
> HMAC ile aranabilir kılar. Soft delete mantığı uygulanır.

```sql
persons
  id                UUID PK
  club_id           UUID FK → clubs.id  NOT NULL   -- tenant

  -- Kimlik
  first_name        VARCHAR(100) NOT NULL
  last_name         VARCHAR(100) NOT NULL
  date_of_birth     DATE
  gender            VARCHAR(20)  CHECK IN ('erkek','kadin','diger','belirtilmedi')
  nationality       VARCHAR(3)   DEFAULT 'TR'

  -- TC Kimlik — Sprint 3.1 (her iki alan birlikte)
  tc_identity_enc   BYTEA        -- pgcrypto AES-256 şifreli; şifresi çözülmüş değer asla loglanmaz
  tc_identity_hmac  VARCHAR(64)  -- HMAC-SHA256 hex; arama/unique kontrolü için

  -- Profil
  profile_photo_url VARCHAR(500)
  notes             TEXT

  -- Soft delete
  is_active         BOOLEAN DEFAULT TRUE
  is_deleted        BOOLEAN DEFAULT FALSE
  deleted_at        TIMESTAMPTZ
  deleted_by        UUID FK → users.id

  created_at        TIMESTAMPTZ DEFAULT now()
  updated_at        TIMESTAMPTZ DEFAULT now()

  -- Composite FK desteği: diğer tablolar (club_id, person_id) ile bu index'e bağlanır
  UNIQUE: (club_id, id)   -- composite FK referansı için; UUID PK ile birlikte tutarlı

  UNIQUE: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
    -- partial: silinen kişi yeniden kaydedilebilir
  INDEX: (club_id, is_deleted)
  INDEX: (club_id, last_name, first_name)
  INDEX: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
```

### users (mevcut tabloya ek)
> Alembic migration: `ALTER TABLE users ADD COLUMN person_id UUID REFERENCES persons(id)`.  
> Bir kullanıcı en fazla 1 kişiyle eşlenir; kişinin kullanıcı hesabı olmayabilir.

```sql
ALTER TABLE users
  ADD COLUMN person_id UUID NULL,
  ADD CONSTRAINT fk_users_person
    FOREIGN KEY (person_id) REFERENCES persons(id)
    ON DELETE SET NULL;

INDEX: (club_id, person_id) WHERE person_id IS NOT NULL
```

### person_capacities
> Kişinin iş kapasitesini (ne yapabildiğini) tanımlar.  
> Auth tablosundaki `role` alanından **bağımsızdır** — birini değiştirmek diğerini etkilemez.

```sql
person_capacities
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID FK → persons.id NOT NULL

  capacity        VARCHAR(50) NOT NULL
    -- 'antrenor','muhasebeci','idareci','teknik_sorumlu','hakem','gonullu'
  start_date      DATE
  end_date        DATE
  notes           TEXT

  assigned_at     TIMESTAMPTZ DEFAULT now()
  assigned_by     UUID FK → users.id
  revoked_at      TIMESTAMPTZ
  revoked_by      UUID FK → users.id

  INDEX: (club_id, person_id)
  INDEX: (club_id, capacity, revoked_at) WHERE revoked_at IS NULL
```

### coach_athlete_assignments
> Antrenör kim, hangi sporcuyu, hangi tarih aralığında antrenman yaptırıyor.

```sql
coach_athlete_assignments
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL

  coach_person_id  UUID FK → persons.id NOT NULL
  athlete_person_id UUID FK → persons.id NOT NULL

  discipline_id    UUID FK → disciplines.id
  start_date       DATE NOT NULL
  end_date         DATE
  is_active        BOOLEAN DEFAULT TRUE
  notes            TEXT

  assigned_at      TIMESTAMPTZ DEFAULT now()
  assigned_by      UUID FK → users.id

  UNIQUE: (club_id, coach_person_id, athlete_person_id, discipline_id)
    WHERE is_active = TRUE
  INDEX: (club_id, coach_person_id, is_active)
  INDEX: (club_id, athlete_person_id, is_active)
```

### memberships
> Kişinin kulüp üyeliğini temsil eder.  
> Üyelik numarası kulüp bazında benzersizdir ve otomatik sıralı üretilir.

```sql
memberships
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID FK → persons.id NOT NULL

  membership_no    VARCHAR(50) NOT NULL
    -- format: MYK-2026-00001 (sıralı, kulüp bazında)

  membership_type  VARCHAR(50) NOT NULL
    CHECK IN ('aktif_sporcu','lisanssiz_sporcu','veli_uye',
              'onursal','personel','misafir','kurumsal')

  status           VARCHAR(20) NOT NULL DEFAULT 'aktif'
    CHECK IN ('aktif','pasif','askida','iptal')

  start_date       DATE NOT NULL
  end_date         DATE
  renewal_date     DATE
  fee_amount       NUMERIC(10,2)
  fee_currency     VARCHAR(3) DEFAULT 'TRY'

  created_at       TIMESTAMPTZ DEFAULT now()
  updated_at       TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, membership_no) WHERE NOT is_deleted
  -- partial: iptal edilmiş no tekrar kullanılabilir
  INDEX: (club_id, status, end_date)
  INDEX: (club_id, person_id)
```

### athletes
> Sporcu profili (lisanssız alanlara odaklanır; lisanslar `person_licenses`'ta).

```sql
athletes
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID FK → persons.id NOT NULL

  competition_level VARCHAR(50)
    CHECK IN ('yerel','bolgesel','ulusal','uluslararasi','milli_takim')

  tyf_registered   BOOLEAN DEFAULT FALSE
  tyf_id           VARCHAR(50)
  elo_score        INT

  is_active        BOOLEAN DEFAULT TRUE
  created_at       TIMESTAMPTZ DEFAULT now()
  updated_at       TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, person_id)
```

### coaches
> Antrenör profili. Lisanslar `person_licenses`'ta.

```sql
coaches
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID FK → persons.id NOT NULL

  license_level    VARCHAR(50)
    -- ('Seviye 1','Seviye 2','Seviye 3','Milli Takım Antrenörü')

  is_active        BOOLEAN DEFAULT TRUE
  created_at       TIMESTAMPTZ DEFAULT now()
  updated_at       TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, person_id)
```

### guardians
> Veli–sporcu ilişkisi. Her iki taraf da `persons` tablosunda.

```sql
guardians
  id                    UUID PK
  club_id               UUID FK → clubs.id  NOT NULL
  guardian_person_id    UUID FK → persons.id NOT NULL
  athlete_person_id     UUID FK → persons.id NOT NULL

  relation_type         VARCHAR(50) CHECK IN ('anne','baba','vasi','kardes','diger')
  is_primary            BOOLEAN DEFAULT FALSE
  emergency_priority    INT DEFAULT 0

  created_at            TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, guardian_person_id, athlete_person_id)
  INDEX: (club_id, athlete_person_id)
  INDEX: (club_id, guardian_person_id)
```

### person_licenses
> Kişi başına N lisans. Sporcu lisansı, antrenör lisansı, hakem lisansı.

```sql
person_licenses
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID FK → persons.id NOT NULL

  license_type    VARCHAR(50) NOT NULL
    CHECK IN ('sporcu_lisansi','antrenor_lisansi','hakem_lisansi','saglik_lisansi','diger')

  license_no      VARCHAR(100) NOT NULL
  federation      VARCHAR(100) DEFAULT 'TYF'
  issued_at       DATE
  expires_at      DATE
  is_active       BOOLEAN DEFAULT TRUE

  -- Opsiyonel: tekne sınıfı (sporcu lisansı için)
  boat_class_id   UUID FK → boat_classes.id

  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, license_type)
  INDEX: (club_id, expires_at) WHERE expires_at IS NOT NULL AND is_active = TRUE
    -- yaklaşan lisans bitimleri için
```

### contact_information
> Telefon, e-posta, sosyal medya. **Adres burada değil** → `addresses` tablosunda.

```sql
contact_information
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID FK → persons.id NOT NULL

  contact_type    VARCHAR(30) NOT NULL
    CHECK IN ('telefon','email','sosyal')   -- 'adres' YOKTUR

  label           VARCHAR(50)
    -- 'ev', 'is', 'mobil', 'kisisel', 'veli', 'instagram', 'twitter'

  value           VARCHAR(500) NOT NULL
  is_primary      BOOLEAN DEFAULT FALSE
  is_verified     BOOLEAN DEFAULT FALSE
  verified_at     TIMESTAMPTZ
  verified_by     UUID FK → users.id

  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, contact_type)
```

### addresses

```sql
addresses
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID FK → persons.id NOT NULL

  label           VARCHAR(50) DEFAULT 'ev'
  address_line1   VARCHAR(200)
  address_line2   VARCHAR(200)
  district        VARCHAR(100)
  city            VARCHAR(100)
  postal_code     VARCHAR(20)
  country         VARCHAR(3)   DEFAULT 'TR'
  is_primary      BOOLEAN DEFAULT FALSE

  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id)
```

### emergency_contacts

```sql
emergency_contacts
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID FK → persons.id NOT NULL

  contact_name    VARCHAR(200) NOT NULL
  relation        VARCHAR(100)
  phone           VARCHAR(50)  NOT NULL
  phone_alt       VARCHAR(50)
  priority        INT DEFAULT 1

  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, priority)
```

### consent_definitions
> Hangi onay türü, hangi metin versiyonuyla istendiğini tanımlar.  
> Güncellenince yeni versiyon eklenir, eski silinmez (audit trail).

```sql
consent_definitions
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL

  consent_key     VARCHAR(100) NOT NULL
    -- 'kvkk_acik_riza', 'saglik_bilgisi', 'fotograf_yayini', 'pazarlama'

  version         INT NOT NULL DEFAULT 1
  title           VARCHAR(200) NOT NULL
  text_content    TEXT NOT NULL        -- kullanıcıya gösterilen tam metin
  is_required     BOOLEAN DEFAULT TRUE
  valid_from      TIMESTAMPTZ DEFAULT now()
  valid_until     TIMESTAMPTZ
  created_by      UUID FK → users.id
  created_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, consent_key, version)
  INDEX: (club_id, consent_key, valid_from)
```

### consent_events
> **Immutable** olay tablosu. Hiçbir zaman UPDATE/DELETE yapılmaz.  
> Kişinin son durumu en yüksek `id` (veya `created_at`) olan kayıttır.

```sql
consent_events
  id                    UUID PK
  club_id               UUID FK → clubs.id  NOT NULL
  person_id             UUID FK → persons.id NOT NULL
  definition_id         UUID FK → consent_definitions.id NOT NULL

  event_type            VARCHAR(20) NOT NULL
    CHECK IN ('verildi','reddedildi','geri_alindi','superseded','expired')
    --
    -- superseded: onay metni yeni versiyona geçince eski onay geçersiz kılınır
    --   örnek: KVKK metni v2 yayınlandığında, v1 consent_event'i 'superseded' olarak
    --   kapatılır; kullanıcıdan v2 için yeni 'verildi' event'i beklenir
    --
    -- expired: bitiş tarihi geçen periyodik onaylar için (örn: yıllık sağlık formu)
    --   sistem tarafından otomatik yazılabilir (scheduled job)

  -- Kim, nasıl, nereden onay verdi
  performed_by          UUID FK → users.id
  performed_at          TIMESTAMPTZ DEFAULT now()
  ip_address            INET
  user_agent            VARCHAR(500)
  channel               VARCHAR(50)
    -- 'web','pdf_imza','yazili_form','telefon','mobil'

  document_ref          VARCHAR(500)  -- imzalı form dosya yolu
  notes                 TEXT

  -- Bu kayıt hiçbir zaman değiştirilemez
  created_at            TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, definition_id, created_at DESC)
  INDEX: (club_id, person_id, event_type, created_at DESC)
```

### person_documents

```sql
person_documents
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID FK → persons.id NOT NULL

  document_type   VARCHAR(100) NOT NULL
    -- 'kimlik_fotokopisi','lisans','sigorta_poliçesi','saglik_raporu',
    --  'veli_izni','ic_yonetmelik_imza','fotograf'

  -- Depolama
  storage_provider VARCHAR(50)  DEFAULT 'local'
    -- 'local','s3','azure_blob'
  storage_key     VARCHAR(500)  -- provider'a özel path veya key
  file_name       VARCHAR(200)
  mime_type       VARCHAR(100)
  file_size_bytes INT
  hash_sha256     VARCHAR(64)   -- dosya bütünlük doğrulaması

  -- Geçerlilik
  valid_from      DATE
  valid_until     DATE
  issued_by       VARCHAR(200)  -- düzenleyen kurum

  -- Meta
  uploaded_by     UUID FK → users.id
  uploaded_at     TIMESTAMPTZ DEFAULT now()
  is_verified     BOOLEAN DEFAULT FALSE
  verified_by     UUID FK → users.id
  verified_at     TIMESTAMPTZ
  notes           TEXT

  -- Soft delete
  is_deleted      BOOLEAN DEFAULT FALSE
  deleted_by      UUID FK → users.id
  deleted_at      TIMESTAMPTZ

  INDEX: (club_id, person_id, document_type)
  INDEX: (club_id, valid_until) WHERE valid_until IS NOT NULL AND is_deleted = FALSE
```

### disciplines
> Referans tablosu. Kulüp bazında veya genel (club_id = NULL).

```sql
disciplines
  id              UUID PK
  club_id         UUID FK → clubs.id NULL   -- NULL = tüm kulüplere uygulanır
  name            VARCHAR(100) NOT NULL
  code            VARCHAR(20)
  is_active       BOOLEAN DEFAULT TRUE
  created_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, code) WHERE club_id IS NOT NULL
  UNIQUE: (code) WHERE club_id IS NULL
```

### boat_classes
> Referans tablosu.

```sql
boat_classes
  id              UUID PK
  club_id         UUID FK → clubs.id NULL
  name            VARCHAR(100) NOT NULL  -- 'Optimist', 'Laser/ILCA 6', '420', 'RS:X'
  code            VARCHAR(20)
  crew_size       INT DEFAULT 1
  min_age         INT
  max_age         INT
  discipline_id   UUID FK → disciplines.id
  is_active       BOOLEAN DEFAULT TRUE
  created_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, code) WHERE club_id IS NOT NULL
  UNIQUE: (code) WHERE club_id IS NULL
```

---

## ER Diyagramı (Metin)

İki kavramsal sistem birbirinden tamamen bağımsızdır:

```
════════════════════════════════════════════════════════════
AUTH SİSTEMİ (Aşama 2 — mevcut)
════════════════════════════════════════════════════════════
clubs ──< users
           │   .role = 'kulup_yonetici' | 'antrenor' | 'sporcu' | ...
           │   .person_id ──────────────────────────────────────────┐
           │                                                         │
           │   Kim ne yapabilir?                                     │
           │   JWT claim → RBAC middleware → endpoint izni          │
           │                                                         │
════════════════════════════════════════════════════════════         │
İŞ ALANI MODELİ (Sprint 3.1 — yeni)                                 │
════════════════════════════════════════════════════════════         │
clubs ──< persons ◄────────────────────────────────────────────────┘
           │   (users.person_id = persons.id — opsiyonel bağlantı)
           │
           │   Kim bu kişi? → persons
           │   Bu kişi ne kapasitede görev alıyor? → person_capacities
           │   (Antrenör olmak, muhasebeci olmak — idari rol, auth role DEĞİL)
           │
           ├──< person_capacities
           │      capacity = 'antrenor' | 'muhasebeci' | 'idareci' | ...
           │      (users.role'den bağımsız — bir kişi hem antrenör
           │       kapasitesinde hem sporcu olabilir)
           │
           ├──< memberships
           │
           ├──< athletes
           │      └── [person_licenses] (license_type='sporcu_lisansi')
           │
           ├──< coaches
           │      └── [person_licenses] (license_type='antrenor_lisansi')
           │
           ├──< guardians >── persons (veli ←→ sporcu)
           │
           ├──< coach_athlete_assignments >── persons (antrenör)
           │         └── disciplines
           │
           ├──< person_licenses >── boat_classes
           │
           ├──< contact_information
           ├──< addresses
           ├──< emergency_contacts
           │
           ├──< consent_events >── consent_definitions
           │
           └──< person_documents

Referans: disciplines ──< boat_classes
```

**Ayrım özeti:**

| Kavram | Tablo | Soru |
|---|---|---|
| Auth rolü | `users.role` | Bu kullanıcı hangi endpoint'lere erişebilir? |
| İş kapasitesi | `person_capacities` | Bu kişi kurumda hangi rolde görev alıyor? |

Bir `kulup_yonetici` auth rolüne sahip kullanıcı, sistemde antrenör kapasitesinde hiç görünmeyebilir; tersine bir `antrenor` kapasitesindeki kişinin sisteme giriş hesabı bile olmayabilir.

---

## Composite FK / Tenant İzolasyonu (DB Seviyesi)

Her tablo `club_id` barındırır. FK'lar şu tutarlı pattern'i izler:

```sql
-- persons tablosunda UUID PK + UNIQUE(club_id, id) — her iki FK tipi için temel:
--   a) Tekil FK: FK person_id → persons.id  (club_id uygulama katmanında kontrol edilir)
--   b) Composite FK: FK (club_id, person_id) → persons(club_id, id)  ← tercih edilen
--
-- UNIQUE(club_id, id) index persons şemasında zaten tanımlı; ayrıca migrate'e eklenmez.

-- Örnek: athletes → persons aynı kulüpte olmak zorunda
ALTER TABLE athletes
  ADD CONSTRAINT fk_athletes_person_same_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id);
-- Bu constraint, farklı kulüpten bir persons kaydına FK bağlanmasını DB seviyesinde engeller.

-- Aynı pattern tüm alt tablolara (memberships, coaches, guardians, vb.) uygulanır.
-- Sonuç: tenant izolasyonu hem uygulama (assert_same_club) hem DB (composite FK) katmanında sağlanır.
```

---

## TC Kimlik Şifreleme — Sprint 3.1 Gereksinimi

TC kimlik numarasının **iki alanda** saklanması zorunludur:

```python
# backend/app/core/tc_identity.py

import hashlib, hmac, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TC_HMAC_KEY = bytes.fromhex(settings.tc_hmac_key)   # 32-byte, .env'de
TC_ENC_KEY  = bytes.fromhex(settings.tc_enc_key)    # 32-byte, .env'de

def encrypt_tc(tc_no: str) -> bytes:
    """AES-256-GCM ile şifrele → BYTEA olarak sakla."""
    aesgcm = AESGCM(TC_ENC_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, tc_no.encode(), None)
    return nonce + ciphertext   # 12 + len bytes

def decrypt_tc(blob: bytes) -> str:
    """Şifreyi çöz. Sonuç asla loglanmaz."""
    aesgcm = AESGCM(TC_ENC_KEY)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()

def hmac_tc(tc_no: str) -> str:
    """HMAC-SHA256 hex — arama ve unique kontrolü için."""
    return hmac.new(TC_HMAC_KEY, tc_no.encode(), hashlib.sha256).hexdigest()
```

`tc_identity_hmac` üzerinden arama yapılır; `tc_identity_enc` yalnızca açıkça istendiğinde `decrypt_tc()` ile okunur. Şifresi çözülmüş TC asla:
- log'a yazılmaz  
- API response'a eklenmez (yalnızca yönetici + açık `?reveal=true` parametresiyle)
- audit_log.details içinde saklanmaz

---

## API Endpoint Listesi

```
# Kişiler
GET    /api/v1/persons                   (filtreleme: rol, aktif, arama)
POST   /api/v1/persons
GET    /api/v1/persons/{id}
PATCH  /api/v1/persons/{id}
DELETE /api/v1/persons/{id}             (soft delete)

# TC okuma (ayrı endpoint, ayrı yetki)
GET    /api/v1/persons/{id}/tc-identity (sadece kulup_yonetici)

# Üyelikler
GET    /api/v1/memberships
POST   /api/v1/memberships
GET    /api/v1/memberships/{id}
PATCH  /api/v1/memberships/{id}

# Sporcu profilleri
GET    /api/v1/athletes
POST   /api/v1/athletes
GET    /api/v1/athletes/{id}
PATCH  /api/v1/athletes/{id}

# Veli ilişkileri
GET    /api/v1/guardians
POST   /api/v1/guardians
DELETE /api/v1/guardians/{id}

# Antrenör profilleri
GET    /api/v1/coaches
POST   /api/v1/coaches
GET    /api/v1/coaches/{id}
PATCH  /api/v1/coaches/{id}

# Antrenör–Sporcu atamaları
GET    /api/v1/coach-assignments
POST   /api/v1/coach-assignments
DELETE /api/v1/coach-assignments/{id}

# Lisanslar
GET    /api/v1/persons/{id}/licenses
POST   /api/v1/persons/{id}/licenses
PATCH  /api/v1/persons/{id}/licenses/{lid}
DELETE /api/v1/persons/{id}/licenses/{lid}

# İletişim
GET    /api/v1/persons/{id}/contacts
POST   /api/v1/persons/{id}/contacts
PATCH  /api/v1/persons/{id}/contacts/{cid}
DELETE /api/v1/persons/{id}/contacts/{cid}

# Adresler
GET    /api/v1/persons/{id}/addresses
POST   /api/v1/persons/{id}/addresses
PATCH  /api/v1/persons/{id}/addresses/{aid}
DELETE /api/v1/persons/{id}/addresses/{aid}

# Onaylar / KVKK (immutable events)
GET    /api/v1/persons/{id}/consents            (son durum)
GET    /api/v1/persons/{id}/consents/history    (tüm olaylar)
POST   /api/v1/persons/{id}/consents            (yeni olay: verildi/reddedildi/geri_alindi)

# Belgeler
GET    /api/v1/persons/{id}/documents
POST   /api/v1/persons/{id}/documents           (upload)
GET    /api/v1/persons/{id}/documents/{did}
DELETE /api/v1/persons/{id}/documents/{did}     (soft delete)

# Referans
GET    /api/v1/disciplines
GET    /api/v1/boat-classes
```

---

## RBAC Matrisi

| Endpoint | kulup_yonetici | antrenor | muhasebe | sporcu | veli | misafir |
|---|---|---|---|---|---|---|
| GET /persons | ✅ tüm kulüp | ✅ atanmış sporcular | ✅ finansal profil | ✅ sadece kendin | ✅ sadece çocuk | ❌ 403 |
| POST /persons | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| PATCH /persons/{id} | ✅ | ✅ antrenman notu | ❌ | ✅ kendi profili | ✅ veli alanları | ❌ |
| DELETE /persons/{id} | ✅ soft delete | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /persons/{id}/tc-identity | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /memberships | ✅ | ✅ | ✅ | ✅ kendi | ✅ çocuk | ❌ |
| GET /athletes | ✅ | ✅ atanmış | ❌ | ✅ kendi | ✅ çocuk | ❌ |
| GET /coach-assignments | ✅ | ✅ kendi atamaları | ❌ | ✅ kendi antrenörü | ✅ çocuk | ❌ |
| POST /coach-assignments | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /persons/{id}/consents | ✅ | ❌ | ❌ | ✅ kendi | ✅ kendi+çocuk | ❌ |
| POST /persons/{id}/consents | ✅ | ❌ | ❌ | ✅ kendi | ✅ çocuk için | ❌ |
| GET /persons/{id}/documents | ✅ | ✅ lisans/sigorta | ❌ | ✅ kendi | ✅ çocuk | ❌ |

> Tüm endpoint'ler: yetki kontrolünden önce `assert_same_club()` — yanlış kulüp → **404** (bilgi sızdırmaz).

---

## Kişisel Veri Sınıflandırması

| Alan | KVKK Kategorisi | Şifreleme | Erişim Kısıtı |
|---|---|---|---|
| `tc_identity_enc` | ÖZEL — Kimlik | AES-256-GCM (pgcrypto) | Yalnızca `kulup_yonetici` |
| `tc_identity_hmac` | Türetilmiş — Arama indeksi | HMAC-SHA256 | DB seviyesi; API'de okunmaz |
| `date_of_birth` | KİŞİSEL | Yok (erişim kontrolü) | Yönetici, antrenör, kendi |
| Sağlık verileri | ÖZEL — Sağlık (Sprint 3.2) | AES-256 | Yönetici + onaylı antrenör |
| Telefon / e-posta | KİŞİSEL | Yok | Yönetici, kendi |
| `profile_photo_url` | KİŞİSEL | Yok | Kulüp içi veya yönetici kararı |
| Consent olayları | KVKK | Yok (audit log) | Yönetici + kendi |
| Finansal bilgiler | KİŞİSEL (Sprint 3.4) | Yok | Yönetici + muhasebe |

---

## Migration Planı

```
0002_persons_core.py
  + persons (tc_identity_enc, tc_identity_hmac dahil)
  + ALTER TABLE users ADD COLUMN person_id

0003_persons_roles_memberships.py
  + person_capacities
  + memberships
  + athletes
  + coaches
  + guardians
  + coach_athlete_assignments

0004_persons_licenses_contacts.py
  + person_licenses
  + contact_information
  + addresses
  + emergency_contacts

0005_consent_events.py
  + consent_definitions
  + consent_events

0006_person_documents.py
  + person_documents

0007_reference_tables.py
  + disciplines
  + boat_classes
  + seed verileri (TYF standart tekne sınıfları, yelken dalları)
```

Her migration `IF NOT EXISTS` **kullanmaz**; Alembic revision zinciri idempotency'yi sağlar.  
`down_revision` doğru chain ile bağlanmalı; `alembic heads` tek head üretmeli.

---

## Test Planı

### Birim Testleri (SQLite, `pytest`)

**`test_persons.py`**
- Kişi oluştur → 201; listeleme → 200
- Soft delete → listede görünmüyor; silinmiş kayıt ayrı endpoint
- Tenant izolasyonu: kulüp A kişisi kulüp B token'ıyla → 404
- TC şifreleme: kaydet → oku → çöz; düz metin DB'de yok
- TC HMAC: aynı TC → aynı HMAC; farklı TC → farklı HMAC
- Duplicate TC (aynı kulüpte) → unique constraint hatası

**`test_memberships.py`**
- Üyelik numarası otomatik artan
- `start_date > end_date` → 422
- Kişisiz üyelik oluşturmaya çalış → 422

**`test_athletes.py`** / **`test_coaches.py`**
- Kişi olmadan sporcu/antrenör profili → 422
- Aynı kişiye 2. sporcu profili → 409

**`test_guardians.py`**
- Veli kendi çocuğu olamaz (`guardian_person_id == athlete_person_id`) → 422
- Veli başkasının çocuğunu göremez → 404

**`test_coach_assignments.py`**
- Antrenör → kendi atanmış sporcusunu görür
- Antrenör → atanmamış sporcu → 404
- Çakışan aktif atama → 409

**`test_consents.py`**
- Olay eklenir; önceki kayıt değişmez (immutable)
- Kişinin son durumu en güncel event'ten hesaplanır
- Geri alınan onayın tarihi kayıtlı

**`test_person_licenses.py`**
- Aynı kişiye birden fazla lisans → OK (different types)
- Süresi geçmiş lisans `is_active=False` flag'i alır

### Entegrasyon Testleri (Docker, `s3_0a_verify.sh` kapsamında)

- pgcrypto extension yüklü (CREATE EXTENSION IF NOT EXISTS pgcrypto)
- TC şifreleme: Docker API container'ında uçtan uca
- Composite FK: farklı kulüpten persons'a FK → DB constraint hatası
- Kriter 30 (`s3_0a_verify.sh`): çapraz tenant → 404

---

## Başlamadan Önce Beklenecek

1. `s3_0a_verify.sh` → exit 0 veya exit 2 (0 FAIL)
2. `sprint3_0a_run.log` kaydedildi
3. Bu REV2 plan onaylandı

> Sprint 3.1 uygulaması bu plan onaylandıktan sonra başlar.  
> Kodlamaya başlamadan önce: `0002_persons_core.py` migration yazılır, `alembic upgrade head` test edilir, ardından model → endpoint → test sırası izlenir.

---

## Gelecek Sprint'ler İçin Açık Kararlar

Aşağıdaki kararlar Sprint 3.1 için blokaj oluşturmaz; belirlenen sprint'te alınmalıdır.

### DDD Mimarisi — Sprint 4 başlamadan önce

Sprint 3.1–3.3 tek domain (persons/memberships/training) kapsar; şimdiki katman yeterli.  
Sprint 4+ (finance, equipment, documents, notifications) devreye girerken:

```
Önerilen geçiş:
  Presentation (routers)
  Application  (services / use-cases)
  Domain       (entities, value objects, domain events)
  Infrastructure (repositories, external adapters)

Domain sınırları:
  MembershipDomain · TrainingDomain · FinanceDomain
  EquipmentDomain  · DocumentDomain · NotificationDomain
```

Karar Sprint 3.3 retrospektifinde alınmalı; Sprint 4 ilk commit'i bu yapıya göre başlamalı.

### boat_class_disciplines N:N — Sprint 3.2 veya 3.3

Şimdiki `boat_class → discipline` (N:1) IQFoil/Formula Kite/Wing gibi çok disiplinli ekipmanlar için yetersiz kalacak.  
Çözüm: `boat_class_disciplines` junction tablosu. Referans verisi az olduğu için migration süresi ihmal edilebilir.

### person_documents scan_status — Sprint 3.6 (Belgeler Sprint'i)

```sql
scan_status  VARCHAR(20) DEFAULT 'pending'
  CHECK IN ('pending','clean','infected','quarantined')
```

Dosya upload endpoint'iyle birlikte; antivirus pipeline entegrasyonuyla eş zamanlı eklenmeli.

### Performans Testleri — Sprint 3.1 tamamlandıktan sonra

```
Hedef yük (k6 veya Locust):
  5.000 persons, 10.000 memberships seed
  500 eş zamanlı login
  500 eş zamanlı refresh
  RBAC endpoint latency < 50ms p95
  Tenant query latency < 100ms p95
```

Sonuçlar `sprint3_1_load_test_report.md` olarak kaydedilmeli; index eksikleri burada ortaya çıkar.

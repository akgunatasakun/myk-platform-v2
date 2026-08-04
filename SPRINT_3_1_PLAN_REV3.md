# Sprint 3.1 — Temel Kişi ve Üyelik Mimarisi (REV3)

**Durum:** BEKLEME — Sprint 3.0-A PASS olduktan sonra başlanacak  
**Önkoşul:** `s3_0a_verify.sh` → exit 0 veya exit 2  
**Revizyon:** REV3 — son tutarlılık düzeltmeleri (5 nokta)

---

## REV2 → REV3 Değişiklikleri

| # | REV2 Sorunu | REV3 Düzeltmesi |
|---|---|---|
| 1 | "18 tablo" — yanlış sayım | 16 yeni tablo + 1 mevcut `users` değişikliği = 17 mimari kapsam |
| 2 | `memberships`: `WHERE NOT is_deleted` partial unique, ancak tabloda `is_deleted` alanı yok | `UNIQUE(club_id, membership_no)` — üyelik no hiçbir zaman tekrar kullanılmaz |
| 3 | `users.person_id`: tekil FK — Tenant A kullanıcısı Tenant B kişisine bağlanabilir | Composite FK: `(club_id, person_id) → persons(club_id, id)`; ON DELETE uygulama katmanında |
| 4 | Consent son durum: "en yüksek UUID id" — UUID kronolojik değil | `ORDER BY performed_at DESC, created_at DESC, id DESC` |
| 5 | `consent_events`: `superseded` hangi eski olayı geçersiz kıldığı belli değil | `supersedes_event_id UUID NULL REFERENCES consent_events(id)` eklendi |

---

## REV1 → REV2 Değişiklikleri (referans)

| # | REV1 Sorunu | REV2 Düzeltmesi |
|---|---|---|
| 1 | "12 tablo + 2 junction" — eksik sayım | 16 yeni tablo (REV3'te düzeltildi) |
| 2 | `tc_identity` Sprint 3.2'ye ertelendi | Sprint 3.1'de: AES-256 (pgcrypto) + HMAC-SHA256 |
| 3 | `users` tablosunun `persons` ile bağlantısı yok | `users.person_id` FK eklendi (REV3'te composite FK yapıldı) |
| 4 | `person_roles` iş rollerini auth rolleriyle karıştırıyor | `person_capacities` ayrı tablo |
| 5 | Antrenör–sporcu ataması yok | `coach_athlete_assignments` eklendi |
| 6 | `membership_type` değerleri gerçekçi değil | Güncel değerler |
| 7 | `contact_information` içinde 'adres' var | CHECK'ten çıkarıldı |
| 8 | `boat_class`, `specializations` serbest metin | `disciplines` + `boat_classes` referans tabloları |
| 9 | Tek lisans per kişi | `person_licenses` ayrı tablo |
| 10 | Composite FK yok | `UNIQUE(club_id, id)` + composite FK pattern |
| 11 | `consents` mutable | `consent_definitions` + `consent_events` immutable model |
| 12 | `person_documents` yetersiz | `hash_sha256`, `storage_provider`, `is_deleted` |
| 13 | Partial unique index yok | `WHERE is_deleted = FALSE` index'ler |
| 14 | Tablo başına dokümantasyon yok | Açıklama + güvenlik notu |
| 15 | Çıktı seti eksik | ER diyagramı, migration, test planı |

---

## Tablo Kapsamı

```
YENİ TABLOLAR (16)
─────────────────────────────────────────────────────────────
Çekirdek (1):
  persons                    — merkezi kişi kaydı (TC encrypted + HMAC)

İş Rolleri / Kapasite (2):
  person_capacities          — iş rolleri (antrenor, muhasebe, idareci...)
  coach_athlete_assignments  — antrenör–sporcu atamaları

Üyelik / Profil (4):
  memberships                — üyelik kaydı (tip, durum, dönem)
  athletes                   — sporcu profili
  coaches                    — antrenör profili
  guardians                  — veli–sporcu ilişkisi

Lisans (1):
  person_licenses            — kişi başına N lisans

İletişim (3):
  contact_information        — telefon, e-posta, sosyal medya
  addresses                  — adresler
  emergency_contacts         — acil durum kişileri

KVKK / Onay (2):
  consent_definitions        — onay şablonları
  consent_events             — immutable olay kaydı

Belgeler (1):
  person_documents           — dosya metadata + hash

Referans (2):
  disciplines                — branş listesi
  boat_classes               — tekne sınıfları

MEVCUT TABLO DEĞİŞİKLİĞİ (1)
─────────────────────────────────────────────────────────────
  users                      — person_id composite FK eklendi
```

---

## Tablo Şemaları

### persons
> Tüm iş modüllerinin köküdür. TC kimlik verisini AES-256 ile şifreler,
> HMAC ile aranabilir kılar. Soft delete mantığı uygulanır.

```sql
persons
  id                UUID PK
  club_id           UUID FK → clubs.id  NOT NULL

  -- Kimlik
  first_name        VARCHAR(100) NOT NULL
  last_name         VARCHAR(100) NOT NULL
  date_of_birth     DATE
  gender            VARCHAR(20)  CHECK IN ('erkek','kadin','diger','belirtilmedi')
  nationality       VARCHAR(3)   DEFAULT 'TR'

  -- TC Kimlik — Sprint 3.1 (her iki alan birlikte zorunlu)
  tc_identity_enc   BYTEA        -- pgcrypto AES-256-GCM şifreli; çözülmüş değer asla loglanmaz
  tc_identity_hmac  VARCHAR(64)  -- HMAC-SHA256 hex; arama ve unique kontrolü için

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

  -- Composite FK desteği: alt tablolar (club_id, person_id) ile bu index'e bağlanır
  UNIQUE: (club_id, id)

  UNIQUE: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
  INDEX: (club_id, is_deleted)
  INDEX: (club_id, last_name, first_name)
  INDEX: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
```

### users (mevcut tabloya değişiklik)
> Alembic: `ALTER TABLE users ADD COLUMN person_id UUID NULL` + composite FK.
> Bir kullanıcı en fazla 1 kişiyle eşlenir; kişinin kullanıcı hesabı olmayabilir.
> Kişi silindiğinde `person_id` bağlantısı uygulama servisinden açıkça kaldırılır
> (ON DELETE CASCADE/SET NULL yerine kontrollü uygulama kodu — club_id'nin NULL'a
> düşmemesi için composite ON DELETE SET NULL kullanılmaz).

```sql
ALTER TABLE users
  ADD COLUMN person_id UUID NULL;

ALTER TABLE users
  ADD CONSTRAINT fk_users_person_same_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id);
    -- ON DELETE: uygulama katmanında yönetilir
    -- Tenant A kullanıcısı → Tenant B kişisi DB seviyesinde imkansız

CREATE INDEX idx_users_club_person
  ON users(club_id, person_id) WHERE person_id IS NOT NULL;
```

### person_capacities
> Kişinin kurumsal kapasitesini tanımlar.
> Auth tablosundaki `role` alanından **tamamen bağımsızdır**.

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

  CONSTRAINT fk_person_capacities_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id)
  INDEX: (club_id, capacity, revoked_at) WHERE revoked_at IS NULL
```

### coach_athlete_assignments
> Antrenör–sporcu atamaları; hangi disiplinde, hangi tarih aralığında.

```sql
coach_athlete_assignments
  id                UUID PK
  club_id           UUID FK → clubs.id  NOT NULL

  coach_person_id   UUID NOT NULL
  athlete_person_id UUID NOT NULL

  discipline_id     UUID FK → disciplines.id
  start_date        DATE NOT NULL
  end_date          DATE
  is_active         BOOLEAN DEFAULT TRUE
  notes             TEXT

  assigned_at       TIMESTAMPTZ DEFAULT now()
  assigned_by       UUID FK → users.id

  CONSTRAINT fk_assignment_coach_club
    FOREIGN KEY (club_id, coach_person_id) REFERENCES persons(club_id, id)
  CONSTRAINT fk_assignment_athlete_club
    FOREIGN KEY (club_id, athlete_person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, coach_person_id, athlete_person_id, discipline_id)
    WHERE is_active = TRUE
  INDEX: (club_id, coach_person_id, is_active)
  INDEX: (club_id, athlete_person_id, is_active)
```

### memberships
> Kişinin kulüp üyeliğini temsil eder.
> Üyelik numarası kulüp bazında **kalıcı olarak benzersizdir** — iptal/pasif sonrası tekrar kullanılmaz.
> Üyelik kaydı fiziksel silinmez; `status = 'iptal'` ile sonlandırılır.

```sql
memberships
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID NOT NULL

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

  CONSTRAINT fk_memberships_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, membership_no)
    -- Kalıcı unique — iptal edilmiş no tekrar kullanılamaz
  INDEX: (club_id, status, end_date)
  INDEX: (club_id, person_id)
```

### athletes
> Sporcu profili. Lisanslar `person_licenses`'ta.

```sql
athletes
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID NOT NULL

  competition_level VARCHAR(50)
    CHECK IN ('yerel','bolgesel','ulusal','uluslararasi','milli_takim')

  tyf_registered   BOOLEAN DEFAULT FALSE
  tyf_id           VARCHAR(50)
  elo_score        INT

  is_active        BOOLEAN DEFAULT TRUE
  created_at       TIMESTAMPTZ DEFAULT now()
  updated_at       TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_athletes_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, person_id)
```

### coaches
> Antrenör profili. Lisanslar `person_licenses`'ta.

```sql
coaches
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID NOT NULL

  license_level    VARCHAR(50)
    -- 'Seviye 1','Seviye 2','Seviye 3','Milli Takım Antrenörü'

  is_active        BOOLEAN DEFAULT TRUE
  created_at       TIMESTAMPTZ DEFAULT now()
  updated_at       TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_coaches_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, person_id)
```

### guardians
> Veli–sporcu ilişkisi. Her iki taraf `persons` tablosunda.

```sql
guardians
  id                    UUID PK
  club_id               UUID FK → clubs.id  NOT NULL
  guardian_person_id    UUID NOT NULL
  athlete_person_id     UUID NOT NULL

  relation_type         VARCHAR(50) CHECK IN ('anne','baba','vasi','kardes','diger')
  is_primary            BOOLEAN DEFAULT FALSE
  emergency_priority    INT DEFAULT 0

  created_at            TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_guardians_guardian_club
    FOREIGN KEY (club_id, guardian_person_id) REFERENCES persons(club_id, id)
  CONSTRAINT fk_guardians_athlete_club
    FOREIGN KEY (club_id, athlete_person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, guardian_person_id, athlete_person_id)
  INDEX: (club_id, athlete_person_id)
  INDEX: (club_id, guardian_person_id)
```

### person_licenses
> Kişi başına N lisans.

```sql
person_licenses
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

  license_type    VARCHAR(50) NOT NULL
    CHECK IN ('sporcu_lisansi','antrenor_lisansi','hakem_lisansi','saglik_lisansi','diger')

  license_no      VARCHAR(100) NOT NULL
  federation      VARCHAR(100) DEFAULT 'TYF'
  issued_at       DATE
  expires_at      DATE
  is_active       BOOLEAN DEFAULT TRUE
  boat_class_id   UUID FK → boat_classes.id

  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_licenses_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, license_type)
  INDEX: (club_id, expires_at) WHERE expires_at IS NOT NULL AND is_active = TRUE
```

### contact_information
> Telefon, e-posta, sosyal medya. **Adres bu tabloda değil.**

```sql
contact_information
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

  contact_type    VARCHAR(30) NOT NULL
    CHECK IN ('telefon','email','sosyal')   -- 'adres' YOKTUR

  label           VARCHAR(50)
  value           VARCHAR(500) NOT NULL
  is_primary      BOOLEAN DEFAULT FALSE
  is_verified     BOOLEAN DEFAULT FALSE
  verified_at     TIMESTAMPTZ
  verified_by     UUID FK → users.id

  created_at      TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_contacts_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, contact_type)
```

### addresses

```sql
addresses
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

  label           VARCHAR(50) DEFAULT 'ev'
  address_line1   VARCHAR(200)
  address_line2   VARCHAR(200)
  district        VARCHAR(100)
  city            VARCHAR(100)
  postal_code     VARCHAR(20)
  country         VARCHAR(3)   DEFAULT 'TR'
  is_primary      BOOLEAN DEFAULT FALSE

  created_at      TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_addresses_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id)
```

### emergency_contacts

```sql
emergency_contacts
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

  contact_name    VARCHAR(200) NOT NULL
  relation        VARCHAR(100)
  phone           VARCHAR(50)  NOT NULL
  phone_alt       VARCHAR(50)
  priority        INT DEFAULT 1

  created_at      TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_emergency_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, priority)
```

### consent_definitions
> Onay şablonları. Versiyon güncellenmesi yeni satır ekler, eskisi silinmez.

```sql
consent_definitions
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL

  consent_key     VARCHAR(100) NOT NULL
    -- 'kvkk_acik_riza','saglik_bilgisi','fotograf_yayini','pazarlama'

  version         INT NOT NULL DEFAULT 1
  title           VARCHAR(200) NOT NULL
  text_content    TEXT NOT NULL
  is_required     BOOLEAN DEFAULT TRUE
  valid_from      TIMESTAMPTZ DEFAULT now()
  valid_until     TIMESTAMPTZ
  created_by      UUID FK → users.id
  created_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, consent_key, version)
  INDEX: (club_id, consent_key, valid_from)
```

### consent_events
> **Immutable** olay tablosu — hiçbir zaman UPDATE/DELETE yapılmaz.
>
> Kişinin **son durumu** şu sorguyla belirlenir:
> ```sql
> SELECT * FROM consent_events
> WHERE club_id = $1 AND person_id = $2 AND definition_id = $3
> ORDER BY performed_at DESC, created_at DESC, id DESC
> LIMIT 1
> ```
> UUID büyüklüğü kronolojik sıra garantilemez; `performed_at` birincil sıralama alanıdır.

```sql
consent_events
  id                    UUID PK
  club_id               UUID FK → clubs.id  NOT NULL
  person_id             UUID NOT NULL
  definition_id         UUID FK → consent_definitions.id NOT NULL

  event_type            VARCHAR(20) NOT NULL
    CHECK IN ('verildi','reddedildi','geri_alindi','superseded','expired')
    --
    -- superseded: definition yeni versiyona geçince eski event geçersiz kılınır.
    --   Uygulama: v2 aktif olduğunda, v1 eventleri için 'superseded' olay yazılır;
    --   kullanıcıdan v2 için yeni 'verildi' beklenir.
    --
    -- expired: periyodik onaylar için (örn: yıllık sağlık formu).
    --   Scheduled job tarafından otomatik yazılır.

  -- Hangi eski olayı geçersiz kıldığı (yalnızca 'superseded' eventleri için)
  supersedes_event_id   UUID NULL
    REFERENCES consent_events(id)
    -- v1 → superseded oluşturulurken supersedes_event_id = v1.id girilir

  -- Kim, nasıl, nereden
  performed_by          UUID FK → users.id
  performed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
  ip_address            INET
  user_agent            VARCHAR(500)
  channel               VARCHAR(50)
    -- 'web','pdf_imza','yazili_form','telefon','mobil'

  document_ref          VARCHAR(500)
  notes                 TEXT

  created_at            TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_consent_events_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, definition_id, performed_at DESC)
  INDEX: (club_id, person_id, event_type, performed_at DESC)
```

### person_documents

```sql
person_documents
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

  document_type   VARCHAR(100) NOT NULL
    -- 'kimlik_fotokopisi','lisans','sigorta_policesi','saglik_raporu',
    --  'veli_izni','ic_yonetmelik_imza','fotograf'

  storage_provider VARCHAR(50)  DEFAULT 'local'
  storage_key      VARCHAR(500)
  file_name        VARCHAR(200)
  mime_type        VARCHAR(100)
  file_size_bytes  INT
  hash_sha256      VARCHAR(64)

  valid_from       DATE
  valid_until      DATE
  issued_by        VARCHAR(200)

  uploaded_by      UUID FK → users.id
  uploaded_at      TIMESTAMPTZ DEFAULT now()
  is_verified      BOOLEAN DEFAULT FALSE
  verified_by      UUID FK → users.id
  verified_at      TIMESTAMPTZ
  notes            TEXT

  is_deleted       BOOLEAN DEFAULT FALSE
  deleted_by       UUID FK → users.id
  deleted_at       TIMESTAMPTZ

  CONSTRAINT fk_documents_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, document_type)
  INDEX: (club_id, valid_until) WHERE valid_until IS NOT NULL AND is_deleted = FALSE
```

### disciplines
> Referans tablosu. `club_id = NULL` → tüm kulüplere uygulanır.

```sql
disciplines
  id              UUID PK
  club_id         UUID FK → clubs.id NULL
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
  name            VARCHAR(100) NOT NULL
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
           │                                                         │ composite FK
           │   Kim ne yapabilir?                                     │ (club_id, person_id)
           │   JWT claim → RBAC middleware → endpoint izni          │ → persons(club_id, id)
           │                                                         │
════════════════════════════════════════════════════════════         │
İŞ ALANI MODELİ (Sprint 3.1 — yeni)                                 │
════════════════════════════════════════════════════════════         │
clubs ──< persons ◄────────────────────────────────────────────────┘
           │
           │   Kim bu kişi? → persons
           │   Kurumda ne kapasitede? → person_capacities (auth role DEĞİL)
           │
           ├──< person_capacities
           │      capacity = 'antrenor' | 'muhasebeci' | 'idareci' | ...
           │
           ├──< memberships
           ├──< athletes ──< person_licenses (sporcu_lisansi)
           ├──< coaches  ──< person_licenses (antrenor_lisansi)
           ├──< guardians >── persons (veli ←→ sporcu)
           ├──< coach_athlete_assignments >── persons (antrenör)
           │         └── disciplines
           ├──< contact_information
           ├──< addresses
           ├──< emergency_contacts
           ├──< consent_events >── consent_definitions
           │      └── supersedes_event_id → consent_events (self-ref)
           └──< person_documents

Referans: disciplines ──< boat_classes
```

**Ayrım özeti:**

| Kavram | Tablo | Soru |
|---|---|---|
| Auth rolü | `users.role` | Bu kullanıcı hangi endpoint'lere erişebilir? |
| İş kapasitesi | `person_capacities` | Bu kişi kurumda hangi rolde görev alıyor? |

Bir `kulup_yonetici` auth rolündeki kullanıcı, antrenör kapasitesinde hiç görünmeyebilir. Bir antrenör kapasitesindeki kişinin sisteme giriş hesabı bile olmayabilir.

---

## Composite FK / Tenant İzolasyonu (DB Seviyesi)

```sql
-- persons: UUID PK + UNIQUE(club_id, id)
-- Alt tablolar composite FK ile aynı kulübe ait olmak zorunda:

-- Tüm tablolarda pattern:
CONSTRAINT fk_<tablo>_person_club
  FOREIGN KEY (club_id, person_id)
  REFERENCES persons (club_id, id)

-- users özel durum: ON DELETE uygulama servisinde
ALTER TABLE users
  ADD CONSTRAINT fk_users_person_same_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id);
-- Kişi silindiğinde: PersonService.delete() → user.person_id = NULL, commit()
-- club_id asla NULL'a düşmez.
```

---

## TC Kimlik Şifreleme — Sprint 3.1 Gereksinimi

```python
# backend/app/core/tc_identity.py
import hashlib, hmac, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TC_HMAC_KEY = bytes.fromhex(settings.tc_hmac_key)  # 32-byte
TC_ENC_KEY  = bytes.fromhex(settings.tc_enc_key)   # 32-byte

def encrypt_tc(tc_no: str) -> bytes:
    aesgcm = AESGCM(TC_ENC_KEY)
    nonce = os.urandom(12)
    return nonce + aesgcm.encrypt(nonce, tc_no.encode(), None)

def decrypt_tc(blob: bytes) -> str:
    """Sonuç asla loglanmaz."""
    aesgcm = AESGCM(TC_ENC_KEY)
    return aesgcm.decrypt(blob[:12], blob[12:], None).decode()

def hmac_tc(tc_no: str) -> str:
    return hmac.new(TC_HMAC_KEY, tc_no.encode(), hashlib.sha256).hexdigest()
```

Şifresi çözülmüş TC asla log'a yazılmaz, API response'a eklenmez, audit_log.details'e girmez.

---

## API Endpoint Listesi

```
# Kişiler
GET    /api/v1/persons
POST   /api/v1/persons
GET    /api/v1/persons/{id}
PATCH  /api/v1/persons/{id}
DELETE /api/v1/persons/{id}              (soft delete)
GET    /api/v1/persons/{id}/tc-identity  (sadece kulup_yonetici)

# Üyelikler
GET    /api/v1/memberships
POST   /api/v1/memberships
GET    /api/v1/memberships/{id}
PATCH  /api/v1/memberships/{id}

# Sporcu / Antrenör / Veli
GET    /api/v1/athletes
POST   /api/v1/athletes
GET    /api/v1/athletes/{id}
PATCH  /api/v1/athletes/{id}

GET    /api/v1/coaches
POST   /api/v1/coaches
GET    /api/v1/coaches/{id}
PATCH  /api/v1/coaches/{id}

GET    /api/v1/guardians
POST   /api/v1/guardians
DELETE /api/v1/guardians/{id}

GET    /api/v1/coach-assignments
POST   /api/v1/coach-assignments
DELETE /api/v1/coach-assignments/{id}

# Lisanslar
GET    /api/v1/persons/{id}/licenses
POST   /api/v1/persons/{id}/licenses
PATCH  /api/v1/persons/{id}/licenses/{lid}
DELETE /api/v1/persons/{id}/licenses/{lid}

# İletişim / Adres
GET    /api/v1/persons/{id}/contacts
POST   /api/v1/persons/{id}/contacts
PATCH  /api/v1/persons/{id}/contacts/{cid}
DELETE /api/v1/persons/{id}/contacts/{cid}

GET    /api/v1/persons/{id}/addresses
POST   /api/v1/persons/{id}/addresses
PATCH  /api/v1/persons/{id}/addresses/{aid}
DELETE /api/v1/persons/{id}/addresses/{aid}

# Onaylar / KVKK
GET    /api/v1/persons/{id}/consents          (son durum — performed_at DESC)
GET    /api/v1/persons/{id}/consents/history  (tüm olaylar)
POST   /api/v1/persons/{id}/consents

# Belgeler
GET    /api/v1/persons/{id}/documents
POST   /api/v1/persons/{id}/documents
GET    /api/v1/persons/{id}/documents/{did}
DELETE /api/v1/persons/{id}/documents/{did}  (soft delete)

# Referans
GET    /api/v1/disciplines
GET    /api/v1/boat-classes
```

---

## RBAC Matrisi

| Endpoint | kulup_yonetici | antrenor | muhasebe | sporcu | veli | misafir |
|---|---|---|---|---|---|---|
| GET /persons | ✅ tüm kulüp | ✅ atanmış sporcular | ✅ finansal profil | ✅ kendin | ✅ çocuk | ❌ |
| POST /persons | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| PATCH /persons/{id} | ✅ | ✅ antrenman notu | ❌ | ✅ kendi | ✅ veli alanları | ❌ |
| DELETE /persons/{id} | ✅ soft | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /tc-identity | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /memberships | ✅ | ✅ | ✅ | ✅ kendi | ✅ çocuk | ❌ |
| GET /athletes | ✅ | ✅ atanmış | ❌ | ✅ kendi | ✅ çocuk | ❌ |
| GET /coach-assignments | ✅ | ✅ kendi | ❌ | ✅ kendi antrenörü | ✅ çocuk | ❌ |
| POST /coach-assignments | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /consents | ✅ | ❌ | ❌ | ✅ kendi | ✅ kendi+çocuk | ❌ |
| POST /consents | ✅ | ❌ | ❌ | ✅ kendi | ✅ çocuk | ❌ |
| GET /documents | ✅ | ✅ lisans/sigorta | ❌ | ✅ kendi | ✅ çocuk | ❌ |

> Yanlış kulüp → **404** (bilgi sızdırmaz). `assert_same_club()` tüm endpoint'lerde yetki kontrolünden önce.

---

## Kişisel Veri Sınıflandırması

| Alan | KVKK Kategorisi | Şifreleme | Erişim |
|---|---|---|---|
| `tc_identity_enc` | ÖZEL — Kimlik | AES-256-GCM | Sadece `kulup_yonetici` |
| `tc_identity_hmac` | Türetilmiş — Arama | HMAC-SHA256 | DB seviyesi; API'de okunmaz |
| `date_of_birth` | KİŞİSEL | Yok | Yönetici, antrenör, kendi |
| Sağlık (Sprint 3.2) | ÖZEL — Sağlık | AES-256 | Yönetici + onaylı antrenör |
| Telefon / e-posta | KİŞİSEL | Yok | Yönetici, kendi |
| Consent olayları | KVKK | Yok | Yönetici + kendi |
| Finansal (Sprint 3.4) | KİŞİSEL | Yok | Yönetici + muhasebe |

---

## Migration Planı

```
0002_persons_core.py
  + persons (tc_identity_enc, tc_identity_hmac, UNIQUE(club_id,id))
  + ALTER TABLE users ADD COLUMN person_id + composite FK

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
  + consent_events (supersedes_event_id dahil)

0006_person_documents.py
  + person_documents

0007_reference_tables.py
  + disciplines
  + boat_classes
  + seed: TYF standart tekne sınıfları, yelken dalları
```

`IF NOT EXISTS` kullanılmaz. `alembic heads` → tek head.

---

## Test Planı

### Birim Testleri

**`test_persons.py`**
- CRUD: oluştur → 201, listele → 200, güncelle, soft delete
- Tenant izolasyonu: kulüp B token'ıyla kulüp A kişisi → 404
- Composite FK: farklı club_id kombinasyonu → DB constraint hatası
- TC şifreleme: kaydet → oku → çöz; düz metin DB'de yok
- TC HMAC: aynı TC → aynı HMAC; farklı TC → farklı HMAC
- Duplicate TC (aynı kulüp) → unique constraint hatası

**`test_memberships.py`**
- Üyelik no otomatik artan; aynı no tekrar kullanılamaz (iptal sonrası)
- `start_date > end_date` → 422
- Kişisiz üyelik → 422

**`test_athletes.py` / `test_coaches.py`**
- Kişisiz profil → 422
- Aynı kişiye 2. profil → 409

**`test_guardians.py`**
- `guardian_person_id == athlete_person_id` → 422
- Başkasının çocuğu → 404

**`test_coach_assignments.py`**
- Atanmış sporcu görünür; atanmamış → 404
- Çakışan aktif atama → 409

**`test_consents.py`**
- Olay immutable — önceki kayıt değişmez
- Son durum `performed_at DESC` sıralamasıyla belirlenir
- `superseded` event'in `supersedes_event_id` alanı dolu
- Geri alınan onay için `performed_at` kayıtlı

**`test_person_licenses.py`**
- Aynı kişiye farklı tipte birden fazla lisans → OK
- Süresi dolmuş lisans `is_active=False`

### Entegrasyon Testleri (Docker)

- pgcrypto extension kurulu
- TC şifreleme uçtan uca (Docker API container'ında)
- Composite FK: farklı kulüpten persons FK → DB constraint hatası
- `s3_0a_verify.sh` kriter 30: çapraz tenant → 404

---

## Başlamadan Önce Beklenecek

1. `s3_0a_verify.sh` → exit 0 veya exit 2 (0 FAIL)
2. `sprint3_0a_run.log` kaydedilmiş
3. Bu REV3 plan onaylandı

> Kodlamaya başlamadan önce: `0002_persons_core.py` migration yazılır,
> `alembic upgrade head` test edilir, ardından model → endpoint → test sırası izlenir.

---

## Gelecek Sprint'ler İçin Açık Kararlar

### DDD Mimarisi — Sprint 4 başlamadan önce

Sprint 3.1–3.3 tek domain; şimdiki katman yeterli. Sprint 4+ için:

```
Presentation (routers) · Application (services) · Domain (entities) · Infrastructure (repos)
Domain sınırları: MembershipDomain · TrainingDomain · FinanceDomain · EquipmentDomain · DocumentDomain
```

Karar Sprint 3.3 retrospektifinde alınmalı.

### boat_class_disciplines N:N — Sprint 3.2 veya 3.3

`boat_class → discipline` (N:1) çok disiplinli ekipmanlar için yetersiz kalacak.
Çözüm: `boat_class_disciplines` junction tablosu.

### person_documents scan_status — Sprint 3.6

```sql
scan_status VARCHAR(20) DEFAULT 'pending'
  CHECK IN ('pending','clean','infected','quarantined')
```

### Performans Testleri — Sprint 3.1 sonrası

```
k6 / Locust hedefleri:
  5.000 persons, 10.000 memberships seed
  500 eş zamanlı login / refresh
  RBAC latency < 50ms p95 · Tenant query < 100ms p95
```

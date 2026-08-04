# Sprint 3.1 — Temel Kişi ve Üyelik Mimarisi (REV4)

**Durum:** BEKLEME — Sprint 3.0-A PASS olduktan sonra başlanacak  
**Önkoşul:** `s3_0a_verify.sh` → exit 0 veya exit 2  
**Revizyon:** REV4 — son iki kritik teknik tutarsızlık kapatıldı

---

## REV3 → REV4 Değişiklikleri

| # | REV3 Sorunu | REV4 Düzeltmesi |
|---|---|---|
| 1 | "pgcrypto AES-256-GCM" ifadesi — şifreleme uygulama katmanında Python `AESGCM` kullanıyor | Tüm "pgcrypto" ifadeleri "application-layer AES-256-GCM" olarak değiştirildi |
| 2 | `pgcrypto extension kurulu` entegrasyon testi — Python şifreleme kullanılırken anlamsız | Kriter kaldırıldı |
| 3 | Anahtar rotasyonu düşünülmemiş | `tc_identity_key_version SMALLINT NOT NULL DEFAULT 1` eklendi; rotasyon süreci belgelendi |
| 4 | `consent_definitions.definition_id` FK tekil — cross-tenant bağlanma mümkün | `UNIQUE(club_id, id)` + composite FK |
| 5 | `consent_events.supersedes_event_id` FK tekil — cross-tenant self-ref mümkün | `UNIQUE(club_id, id)` + composite FK |
| 6 | `superseded` event'i için `supersedes_event_id` zorunluluğu DB'de garanti edilmiyor | `CHECK (event_type='superseded' AND id IS NOT NULL) OR (event_type<>'superseded' AND id IS NULL)` |
| 7 | `performed_at` tek alan — hukuki yürürlük tarihi ile kayıt zamanı karışıyor | `effective_at` (iş/hukuki zaman) + `recorded_at` (sistem immutable zaman) ayrıldı |
| 8 | Consent son durum sıralaması `performed_at` üzerinden — alan kaldırıldı | `ORDER BY effective_at DESC, recorded_at DESC, id DESC` |

---

## REV1–REV3 Değişiklikleri (özet referans)

REV1→REV2: 15 mimari sorun (tablo sayımı, tc_identity, users.person_id, person_capacities, coach_athlete_assignments, person_licenses, consent modeli, composite FK, vb.)  
REV2→REV3: 5 tutarsızlık (tablo sayısı 17, memberships unique, users composite FK, consent sıralama, supersedes_event_id)

---

## Tablo Kapsamı

```
YENİ TABLOLAR (16)
─────────────────────────────────────────────────────────────
Çekirdek (1):
  persons                    — merkezi kişi (TC: app-layer AES-256-GCM + HMAC)

İş Rolleri / Kapasite (2):
  person_capacities          — kurumsal görev (auth role'dan bağımsız)
  coach_athlete_assignments  — antrenör–sporcu atamaları

Üyelik / Profil (4):
  memberships                — üyelik kaydı
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
> Tüm iş modüllerinin köküdür. TC kimlik verisi **uygulama katmanında**
> AES-256-GCM ile şifrelenir; PostgreSQL yalnızca şifreli BYTEA ve HMAC hash saklar.
> Anahtar rotasyonu için `tc_identity_key_version` alanı bulunur.

```sql
persons
  id                      UUID PK
  club_id                 UUID FK → clubs.id  NOT NULL

  -- Kimlik
  first_name              VARCHAR(100) NOT NULL
  last_name               VARCHAR(100) NOT NULL
  date_of_birth           DATE
  gender                  VARCHAR(20)  CHECK IN ('erkek','kadin','diger','belirtilmedi')
  nationality             VARCHAR(3)   DEFAULT 'TR'

  -- TC Kimlik — application-layer AES-256-GCM (NOT pgcrypto)
  tc_identity_enc         BYTEA        -- nonce(12B) || ciphertext; Python cryptography.AESGCM
  tc_identity_hmac        VARCHAR(64)  -- HMAC-SHA256 hex; arama ve unique kontrolü
  tc_identity_key_version SMALLINT NOT NULL DEFAULT 1
    -- Aktif key version. Rotasyon: yeni kayıtlar yeni version ile şifrelenir;
    -- eski kayıtlar arka plan job'ı ile yeniden şifrelenir.
    -- Tüm kayıtlar yeni version'a taşınmadan eski anahtar silinmez.

  -- Profil
  profile_photo_url       VARCHAR(500)
  notes                   TEXT

  -- Soft delete
  is_active               BOOLEAN DEFAULT TRUE
  is_deleted              BOOLEAN DEFAULT FALSE
  deleted_at              TIMESTAMPTZ
  deleted_by              UUID FK → users.id

  created_at              TIMESTAMPTZ DEFAULT now()
  updated_at              TIMESTAMPTZ DEFAULT now()

  -- Composite FK desteği: alt tablolar (club_id, person_id) ile bu index'e bağlanır
  UNIQUE: (club_id, id)

  UNIQUE: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
  INDEX: (club_id, is_deleted)
  INDEX: (club_id, last_name, first_name)
  INDEX: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
  INDEX: (tc_identity_key_version) WHERE tc_identity_enc IS NOT NULL
    -- rotasyon job'ı hangi kayıtların eski version kullandığını verimli bulur
```

### users (mevcut tabloya değişiklik)
> Composite FK: Tenant A kullanıcısı Tenant B kişisine DB seviyesinde bağlanamaz.
> Kişi silindiğinde bağlantı `PersonService.delete()` içinde açıkça kaldırılır.

```sql
ALTER TABLE users
  ADD COLUMN person_id UUID NULL;

ALTER TABLE users
  ADD CONSTRAINT fk_users_person_same_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id);

CREATE INDEX idx_users_club_person
  ON users(club_id, person_id) WHERE person_id IS NOT NULL;
```

### person_capacities
> Kurumsal görev tanımı. Auth `users.role`'dan tamamen bağımsız.

```sql
person_capacities
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

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
> Üyelik numarası kulüp bazında **kalıcı benzersizdir** — iptal sonrası tekrar kullanılmaz.
> Fiziksel silme yoktur; `status = 'iptal'` ile sonlandırılır.

```sql
memberships
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID NOT NULL

  membership_no    VARCHAR(50) NOT NULL

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
  INDEX: (club_id, status, end_date)
  INDEX: (club_id, person_id)
```

### athletes

```sql
athletes
  id                UUID PK
  club_id           UUID FK → clubs.id  NOT NULL
  person_id         UUID NOT NULL

  competition_level VARCHAR(50)
    CHECK IN ('yerel','bolgesel','ulusal','uluslararasi','milli_takim')
  tyf_registered    BOOLEAN DEFAULT FALSE
  tyf_id            VARCHAR(50)
  elo_score         INT
  is_active         BOOLEAN DEFAULT TRUE

  created_at        TIMESTAMPTZ DEFAULT now()
  updated_at        TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_athletes_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, person_id)
```

### coaches

```sql
coaches
  id            UUID PK
  club_id       UUID FK → clubs.id  NOT NULL
  person_id     UUID NOT NULL

  license_level VARCHAR(50)
  is_active     BOOLEAN DEFAULT TRUE

  created_at    TIMESTAMPTZ DEFAULT now()
  updated_at    TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_coaches_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, person_id)
```

### guardians

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

```sql
contact_information
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL

  contact_type    VARCHAR(30) NOT NULL CHECK IN ('telefon','email','sosyal')
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
> Onay şablonları. Versiyon artışı yeni satır ekler; eski satır silinmez.

```sql
consent_definitions
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL

  consent_key     VARCHAR(100) NOT NULL
  version         INT NOT NULL DEFAULT 1
  title           VARCHAR(200) NOT NULL
  text_content    TEXT NOT NULL
  is_required     BOOLEAN DEFAULT TRUE
  valid_from      TIMESTAMPTZ DEFAULT now()
  valid_until     TIMESTAMPTZ
  created_by      UUID FK → users.id
  created_at      TIMESTAMPTZ DEFAULT now()

  -- Composite FK desteği: consent_events bu index'e bağlanır
  UNIQUE: (club_id, id)

  UNIQUE: (club_id, consent_key, version)
  INDEX: (club_id, consent_key, valid_from)
```

### consent_events
> **Immutable** olay tablosu — hiçbir zaman UPDATE/DELETE yapılmaz.
>
> **Zaman semantiği:**
> - `effective_at`: olayın hukuken/iş bakımından yürürlüğe girdiği zaman.
>   Geçmişe dönük onay girişinde bu alan geçmiş tarih olabilir.
> - `recorded_at`: olayın sistemde immutable olarak kaydedildiği zaman (DEFAULT now(), değiştirilemez).
>
> **Mevcut durum sorgusu** — her zaman `effective_at` öncelikli:
> ```sql
> SELECT * FROM consent_events
> WHERE club_id = $1 AND person_id = $2 AND definition_id = $3
> ORDER BY effective_at DESC, recorded_at DESC, id DESC
> LIMIT 1
> ```

```sql
consent_events
  id                    UUID PK
  club_id               UUID FK → clubs.id  NOT NULL
  person_id             UUID NOT NULL
  definition_id         UUID NOT NULL   -- composite FK aşağıda

  event_type            VARCHAR(20) NOT NULL
    CHECK IN ('verildi','reddedildi','geri_alindi','superseded','expired')

  -- Hangi eski event'i geçersiz kıldığı (SADECE event_type='superseded' için)
  supersedes_event_id   UUID NULL       -- composite FK aşağıda

  -- Zaman: iş yürürlüğü vs. kayıt zamanı
  effective_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    -- Onayın hukuken/iş bakımından yürürlüğe girdiği zaman
    -- Geçmişe dönük girişte farklı olabilir
  recorded_at           TIMESTAMPTZ NOT NULL DEFAULT now()
    -- Sistemde immutable kayıt zamanı; uygulama asla override etmez

  -- Bağlam
  performed_by          UUID FK → users.id
  ip_address            INET
  user_agent            VARCHAR(500)
  channel               VARCHAR(50) CHECK IN ('web','pdf_imza','yazili_form','telefon','mobil')
  document_ref          VARCHAR(500)
  notes                 TEXT

  -- Composite FK desteği: supersedes_event_id bu index'e bağlanır
  UNIQUE: (club_id, id)

  -- Composite FK: definition aynı kulüpte olmalı
  CONSTRAINT fk_consent_events_definition_club
    FOREIGN KEY (club_id, definition_id)
    REFERENCES consent_definitions (club_id, id)

  -- Composite FK: person aynı kulüpte olmalı
  CONSTRAINT fk_consent_events_person_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id)

  -- Composite FK: supersedes_event aynı kulüpte olmalı
  CONSTRAINT fk_consent_events_supersedes_club
    FOREIGN KEY (club_id, supersedes_event_id)
    REFERENCES consent_events (club_id, id)

  -- İş kuralı: superseded → id zorunlu; diğerleri → id NULL
  CONSTRAINT chk_supersedes_consistency CHECK (
    (event_type = 'superseded' AND supersedes_event_id IS NOT NULL)
    OR
    (event_type <> 'superseded' AND supersedes_event_id IS NULL)
  )

  INDEX: (club_id, person_id, definition_id, effective_at DESC)
  INDEX: (club_id, person_id, event_type, effective_at DESC)
  INDEX: (club_id, recorded_at)   -- denetim sorguları için
```

### person_documents

```sql
person_documents
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID NOT NULL

  document_type    VARCHAR(100) NOT NULL
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

## TC Kimlik Şifreleme — Application-Layer AES-256-GCM

> **pgcrypto extension KULLANILMAZ.** PostgreSQL yalnız şifreli BYTEA ve HMAC değerini saklar.
> Şifreleme/çözme Python `cryptography` kütüphanesinde gerçekleşir.

```python
# backend/app/core/tc_identity.py
import hashlib, hmac, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Anahtarlar env/secret manager'dan; asla kaynak koduna yazılmaz
# settings.tc_enc_keys: Dict[int, bytes]  — {version: 32-byte-key}
# settings.tc_hmac_key: bytes             — 32-byte

def encrypt_tc(tc_no: str, key_version: int) -> bytes:
    """AES-256-GCM ile şifrele. Çıktı: nonce(12B) || ciphertext."""
    key = settings.tc_enc_keys[key_version]
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aesgcm.encrypt(nonce, tc_no.encode(), None)

def decrypt_tc(blob: bytes, key_version: int) -> str:
    """Şifreyi çöz. Sonuç asla loglanmaz veya cache'lenmez."""
    key = settings.tc_enc_keys[key_version]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(blob[:12], blob[12:], None).decode()

def hmac_tc(tc_no: str) -> str:
    """HMAC-SHA256 hex — arama ve unique constraint için."""
    return hmac.new(settings.tc_hmac_key, tc_no.encode(), hashlib.sha256).hexdigest()
```

### Anahtar Rotasyonu

```
1. Yeni anahtar versiyonu (örn: v2) env/secret manager'a eklenir.
2. settings.TC_ENC_KEY_ACTIVE_VERSION = 2 yapılır.
3. Yeni kayıtlar version=2 ile şifrelenir.
4. Arka plan job'ı:
     SELECT id FROM persons WHERE tc_identity_key_version < 2
     batch(100) → decrypt(version=1) → encrypt(version=2) → UPDATE
5. Tüm kayıtlar version=2'ye geçene kadar v1 anahtarı SAKLANIR.
6. Tüm kayıtlar taşındıktan sonra:
     alembic migration → CHECK (tc_identity_key_version = 2)
   ardından v1 anahtarı env'den kaldırılır.
```

`tc_identity_enc` ve `tc_identity_hmac` asla:
- log'a yazılmaz
- API response'a eklenmez (yalnızca `/tc-identity` endpoint'i, sadece `kulup_yonetici`)
- `audit_log.details` içine girmez

---

## ER Diyagramı (Metin)

```
════════════════════════════════════════════════════════════
AUTH SİSTEMİ (Aşama 2 — mevcut)
════════════════════════════════════════════════════════════
clubs ──< users
           │   .role = 'kulup_yonetici' | 'antrenor' | ...
           │   .person_id (composite FK) ─────────────────────┐
           │   JWT claim → RBAC middleware → endpoint izni     │
════════════════════════════════════════════════════════════  │
İŞ ALANI MODELİ (Sprint 3.1 — yeni)                          │
════════════════════════════════════════════════════════════  │
clubs ──< persons ◄──────────────────────────────────────────┘
           │  .tc_identity_enc (app-layer AES-256-GCM)
           │  .tc_identity_key_version
           │
           ├──< person_capacities      (kurumsal görev, auth role DEĞİL)
           ├──< memberships
           ├──< athletes ──< person_licenses (sporcu_lisansi)
           ├──< coaches  ──< person_licenses (antrenor_lisansi)
           ├──< guardians >── persons (veli ←→ sporcu)
           ├──< coach_athlete_assignments >── persons (antrenör)
           │         └── disciplines
           ├──< contact_information
           ├──< addresses
           ├──< emergency_contacts
           ├──< consent_events ──> consent_definitions
           │      └── supersedes_event_id → consent_events (self-ref, composite FK)
           └──< person_documents

Referans: disciplines ──< boat_classes
```

**Ayrım özeti:**

| Kavram | Tablo | Soru |
|---|---|---|
| Auth rolü | `users.role` | Bu kullanıcı hangi endpoint'e erişebilir? |
| Kurumsal görev | `person_capacities` | Bu kişi kurumda ne kapasitesinde? |

---

## Composite FK / Tenant İzolasyonu

```sql
-- persons: UNIQUE(club_id, id)
-- consent_definitions: UNIQUE(club_id, id)
-- consent_events: UNIQUE(club_id, id)  -- self-ref FK için
--
-- Alt tablolar composite FK:
CONSTRAINT fk_<tablo>_person_club
  FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

-- consent özel:
FOREIGN KEY (club_id, definition_id)   REFERENCES consent_definitions(club_id, id)
FOREIGN KEY (club_id, supersedes_event_id) REFERENCES consent_events(club_id, id)
```

---

## API Endpoint Listesi

```
GET/POST       /api/v1/persons
GET/PATCH/DEL  /api/v1/persons/{id}
GET            /api/v1/persons/{id}/tc-identity      (kulup_yonetici)

GET/POST       /api/v1/memberships
GET/PATCH      /api/v1/memberships/{id}

GET/POST       /api/v1/athletes
GET/PATCH      /api/v1/athletes/{id}
GET/POST       /api/v1/coaches
GET/PATCH      /api/v1/coaches/{id}
GET/POST       /api/v1/guardians
DEL            /api/v1/guardians/{id}
GET/POST       /api/v1/coach-assignments
DEL            /api/v1/coach-assignments/{id}

GET/POST/PATCH/DEL  /api/v1/persons/{id}/licenses/{lid?}
GET/POST/PATCH/DEL  /api/v1/persons/{id}/contacts/{cid?}
GET/POST/PATCH/DEL  /api/v1/persons/{id}/addresses/{aid?}

GET            /api/v1/persons/{id}/consents          (son durum — effective_at DESC)
GET            /api/v1/persons/{id}/consents/history  (tüm olaylar)
POST           /api/v1/persons/{id}/consents

GET/POST       /api/v1/persons/{id}/documents
GET/DEL        /api/v1/persons/{id}/documents/{did}

GET            /api/v1/disciplines
GET            /api/v1/boat-classes
```

---

## RBAC Matrisi

| Endpoint | kulup_yonetici | antrenor | muhasebe | sporcu | veli | misafir |
|---|---|---|---|---|---|---|
| GET /persons | ✅ tüm | ✅ atanmış | ✅ finansal | ✅ kendin | ✅ çocuk | ❌ |
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

> Yanlış kulüp → **404**. `assert_same_club()` tüm endpoint'lerde yetki kontrolünden önce.

---

## Kişisel Veri Sınıflandırması

| Alan | KVKK Kategorisi | Şifreleme | Erişim |
|---|---|---|---|
| `tc_identity_enc` | ÖZEL — Kimlik | App-layer AES-256-GCM | Sadece `kulup_yonetici` |
| `tc_identity_hmac` | Türetilmiş — Arama | HMAC-SHA256 | DB seviyesi; API'de okunmaz |
| `tc_identity_key_version` | Teknik meta | — | Yalnız rotasyon job'ı |
| `date_of_birth` | KİŞİSEL | Yok | Yönetici, antrenör, kendi |
| Sağlık (Sprint 3.2) | ÖZEL — Sağlık | AES-256 | Yönetici + onaylı antrenör |
| Telefon / e-posta | KİŞİSEL | Yok | Yönetici, kendi |
| Consent olayları | KVKK | Yok | Yönetici + kendi |
| Finansal (Sprint 3.4) | KİŞİSEL | Yok | Yönetici + muhasebe |

---

## Migration Planı

```
0002_persons_core.py
  + persons (tc_identity_enc, tc_identity_hmac, tc_identity_key_version, UNIQUE(club_id,id))
  + ALTER TABLE users ADD person_id + composite FK

0003_persons_roles_memberships.py
  + person_capacities
  + memberships
  + athletes + coaches + guardians + coach_athlete_assignments

0004_persons_licenses_contacts.py
  + person_licenses + contact_information + addresses + emergency_contacts

0005_consent_events.py
  + consent_definitions (UNIQUE(club_id,id))
  + consent_events (UNIQUE(club_id,id), composite FK'lar, CHECK constraint,
                    effective_at, recorded_at, supersedes_event_id)

0006_person_documents.py
  + person_documents

0007_reference_tables.py
  + disciplines + boat_classes + seed verileri
```

`IF NOT EXISTS` kullanılmaz. `alembic heads` → tek head.

---

## Test Planı

### Birim Testleri

**`test_persons.py`**
- CRUD: oluştur → 201, listele → 200, güncelle, soft delete
- Tenant izolasyonu: kulüp B token'ı → kulüp A kişisi → 404
- Composite FK: farklı club_id → DB constraint hatası
- TC şifreleme: kaydet → oku → çöz; düz metin DB'de yok
- TC HMAC: aynı TC → aynı HMAC; farklı TC → farklı HMAC
- Duplicate TC (aynı kulüp) → unique constraint hatası
- Key version: yeni kayıt aktif versiyonla şifrelenir
- Key version: farklı versiyonla çözme çalışır

**`test_memberships.py`**
- Üyelik no otomatik artan; iptal sonrası aynı no → unique violation
- `start_date > end_date` → 422

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
- Son durum `effective_at DESC` sıralamasıyla belirlenir
- Geçmişe dönük `effective_at` → sıralama doğru
- `superseded` event: `supersedes_event_id` dolu, composite FK doğru tenant
- `superseded` event kendi kendini işaret edemez (`id = supersedes_event_id` → hata)
- Başka tenant'ın event'i supersede edilemez (composite FK hatası)
- `superseded` dışı event tipinde `supersedes_event_id` gönderilirse → CHECK constraint hatası
- `superseded` event'inde `supersedes_event_id = NULL` → CHECK constraint hatası
- `recorded_at` uygulama tarafından override edilemez (DEFAULT now(), sadece DB)
- `effective_at != recorded_at` → geçmiş tarihli onay girişi kabul edilir

**`test_person_licenses.py`**
- Aynı kişiye farklı tipte birden fazla lisans → OK
- Süresi dolmuş lisans `is_active=False`

### Entegrasyon Testleri (Docker)

- TC şifreleme uçtan uca (Docker API container'ında Python AESGCM)
- Key version=1 ile şifrele → decrypt → doğru değer
- Composite FK: farklı kulüpten persons FK → DB constraint hatası
- `consent_events` CHECK constraint: superseded + NULL id → DB hatası
- Composite FK: farklı kulüp definition'ı → DB constraint hatası
- `s3_0a_verify.sh` kriter 30: çapraz tenant → 404

---

## Başlamadan Önce Beklenecek

1. `s3_0a_verify.sh` → exit 0 veya exit 2 (0 FAIL)
2. `sprint3_0a_run.log` kaydedilmiş
3. **Bu REV4 planı onaylandı**

> Kodlamaya başlamadan önce: `0002_persons_core.py` migration yazılır,
> `alembic upgrade head` test edilir, ardından model → endpoint → test sırası izlenir.

---

## Gelecek Sprint'ler İçin Açık Kararlar

### DDD Mimarisi — Sprint 4 başlamadan önce

Sprint 3.1–3.3 tek domain; mevcut katman yeterli. Sprint 4+ için:
```
Presentation · Application · Domain · Infrastructure
Domain sınırları: Membership · Training · Finance · Equipment · Document
```
Karar Sprint 3.3 retrospektifinde alınmalı.

### boat_class_disciplines N:N — Sprint 3.2 veya 3.3

Çok disiplinli ekipmanlar için `boat_class_disciplines` junction tablosu.

### person_documents scan_status — Sprint 3.6

```sql
scan_status VARCHAR(20) DEFAULT 'pending'
  CHECK IN ('pending','clean','infected','quarantined')
```

### Performans Testleri — Sprint 3.1 sonrası

```
k6 / Locust: 5.000 persons · 10.000 memberships seed
500 eş zamanlı login/refresh · RBAC < 50ms p95 · Tenant query < 100ms p95
```

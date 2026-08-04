# Sprint 3.1 — Temel Kişi ve Üyelik Mimarisi (REV4 FINAL)

**Durum:** BEKLEME — Sprint 3.0-A PASS olduktan sonra başlanacak  
**Önkoşul:** `s3_0a_verify.sh` → exit 0 veya exit 2  
**Revizyon:** REV4 FINAL — 3 DB enforcement garantisi + AES-GCM AAD bağlamı

---

## REV4 → REV4 FINAL Değişiklikleri

| # | REV4 Vaadi | REV4 FINAL Garantisi |
|---|---|---|
| 1 | `recorded_at DEFAULT now()` — uygulama override edebilir | BEFORE INSERT trigger: `NEW.recorded_at := clock_timestamp()` — API değeri yok sayılır |
| 2 | "Event kendisini supersede edemez" — sadece test planında | `CONSTRAINT chk_consent_not_self_supersede CHECK (supersedes_event_id IS NULL OR supersedes_event_id <> id)` |
| 3 | "Hiçbir zaman UPDATE/DELETE yapılmaz" — sadece dokümanda | BEFORE UPDATE/DELETE trigger: `RAISE EXCEPTION 'consent_events is immutable'` |
| 4 | `aesgcm.encrypt(nonce, tc_no, None)` — ciphertext başka satıra taşınabilir | AAD bağlamı: `f"{club_id}:{person_id}:{key_version}"` — yanlış kişi/kulübe taşınan ciphertext decrypt edilemez |

---

## Önceki Revizyonlar (özet)

REV1→REV2: 15 mimari sorun (tablo mimarisi, TC kimlik, composite FK, consent model, vb.)  
REV2→REV3: 5 tutarsızlık (tablo sayısı, memberships unique, users composite FK, consent sıralama, supersedes_event_id)  
REV3→REV4: TC pgcrypto→app-layer AES, key_version, consent composite FK, effective_at/recorded_at ayrımı  
REV4→FINAL: 3 DB trigger + AAD

---

## Tablo Kapsamı

```
YENİ TABLOLAR (16)
─────────────────────────────────────────────────────────────
Çekirdek (1):       persons
İş Rolleri (2):     person_capacities, coach_athlete_assignments
Üyelik/Profil (4):  memberships, athletes, coaches, guardians
Lisans (1):         person_licenses
İletişim (3):       contact_information, addresses, emergency_contacts
KVKK/Onay (2):      consent_definitions, consent_events
Belgeler (1):       person_documents
Referans (2):       disciplines, boat_classes

MEVCUT TABLO DEĞİŞİKLİĞİ (1)
─────────────────────────────────────────────────────────────
  users — person_id composite FK eklendi
```

---

## Tablo Şemaları

### persons

```sql
persons
  id                      UUID PK
  club_id                 UUID FK → clubs.id  NOT NULL

  first_name              VARCHAR(100) NOT NULL
  last_name               VARCHAR(100) NOT NULL
  date_of_birth           DATE
  gender                  VARCHAR(20) CHECK IN ('erkek','kadin','diger','belirtilmedi')
  nationality             VARCHAR(3)  DEFAULT 'TR'

  -- TC Kimlik — application-layer AES-256-GCM (pgcrypto KULLANILMAZ)
  tc_identity_enc         BYTEA        -- nonce(12B) || ciphertext
  tc_identity_hmac        VARCHAR(64)  -- HMAC-SHA256 hex
  tc_identity_key_version SMALLINT NOT NULL DEFAULT 1

  profile_photo_url       VARCHAR(500)
  notes                   TEXT

  is_active               BOOLEAN DEFAULT TRUE
  is_deleted              BOOLEAN DEFAULT FALSE
  deleted_at              TIMESTAMPTZ
  deleted_by              UUID FK → users.id

  created_at              TIMESTAMPTZ DEFAULT now()
  updated_at              TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, id)
  UNIQUE: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
  INDEX: (club_id, is_deleted)
  INDEX: (club_id, last_name, first_name)
  INDEX: (club_id, tc_identity_hmac) WHERE tc_identity_hmac IS NOT NULL
  INDEX: (tc_identity_key_version) WHERE tc_identity_enc IS NOT NULL
```

### users (mevcut tabloya değişiklik)

```sql
ALTER TABLE users
  ADD COLUMN person_id UUID NULL;

ALTER TABLE users
  ADD CONSTRAINT fk_users_person_same_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id);

CREATE INDEX idx_users_club_person
  ON users(club_id, person_id) WHERE person_id IS NOT NULL;
-- Kişi silindiğinde PersonService.delete() → user.person_id = NULL, commit()
```

### person_capacities

```sql
person_capacities
  id           UUID PK
  club_id      UUID FK → clubs.id  NOT NULL
  person_id    UUID NOT NULL
  capacity     VARCHAR(50) NOT NULL
  start_date   DATE
  end_date     DATE
  notes        TEXT
  assigned_at  TIMESTAMPTZ DEFAULT now()
  assigned_by  UUID FK → users.id
  revoked_at   TIMESTAMPTZ
  revoked_by   UUID FK → users.id

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

  UNIQUE: (club_id, coach_person_id, athlete_person_id, discipline_id) WHERE is_active = TRUE
  INDEX: (club_id, coach_person_id, is_active)
  INDEX: (club_id, athlete_person_id, is_active)
```

### memberships

```sql
memberships
  id              UUID PK
  club_id         UUID FK → clubs.id  NOT NULL
  person_id       UUID NOT NULL
  membership_no   VARCHAR(50) NOT NULL
  membership_type VARCHAR(50) NOT NULL
    CHECK IN ('aktif_sporcu','lisanssiz_sporcu','veli_uye','onursal','personel','misafir','kurumsal')
  status          VARCHAR(20) NOT NULL DEFAULT 'aktif'
    CHECK IN ('aktif','pasif','askida','iptal')
  start_date      DATE NOT NULL
  end_date        DATE
  renewal_date    DATE
  fee_amount      NUMERIC(10,2)
  fee_currency    VARCHAR(3) DEFAULT 'TRY'
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_memberships_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  UNIQUE: (club_id, membership_no)   -- kalıcı; iptal sonrası tekrar kullanılmaz
  INDEX: (club_id, status, end_date)
  INDEX: (club_id, person_id)
```

### athletes

```sql
athletes
  id                UUID PK
  club_id           UUID FK → clubs.id  NOT NULL
  person_id         UUID NOT NULL
  competition_level VARCHAR(50) CHECK IN ('yerel','bolgesel','ulusal','uluslararasi','milli_takim')
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
  id            UUID PK
  club_id       UUID FK → clubs.id  NOT NULL
  person_id     UUID NOT NULL
  contact_type  VARCHAR(30) NOT NULL CHECK IN ('telefon','email','sosyal')
  label         VARCHAR(50)
  value         VARCHAR(500) NOT NULL
  is_primary    BOOLEAN DEFAULT FALSE
  is_verified   BOOLEAN DEFAULT FALSE
  verified_at   TIMESTAMPTZ
  verified_by   UUID FK → users.id
  created_at    TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_contacts_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, contact_type)
```

### addresses

```sql
addresses
  id            UUID PK
  club_id       UUID FK → clubs.id  NOT NULL
  person_id     UUID NOT NULL
  label         VARCHAR(50) DEFAULT 'ev'
  address_line1 VARCHAR(200)
  address_line2 VARCHAR(200)
  district      VARCHAR(100)
  city          VARCHAR(100)
  postal_code   VARCHAR(20)
  country       VARCHAR(3) DEFAULT 'TR'
  is_primary    BOOLEAN DEFAULT FALSE
  created_at    TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_addresses_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id)
```

### emergency_contacts

```sql
emergency_contacts
  id           UUID PK
  club_id      UUID FK → clubs.id  NOT NULL
  person_id    UUID NOT NULL
  contact_name VARCHAR(200) NOT NULL
  relation     VARCHAR(100)
  phone        VARCHAR(50) NOT NULL
  phone_alt    VARCHAR(50)
  priority     INT DEFAULT 1
  created_at   TIMESTAMPTZ DEFAULT now()

  CONSTRAINT fk_emergency_person_club
    FOREIGN KEY (club_id, person_id) REFERENCES persons(club_id, id)

  INDEX: (club_id, person_id, priority)
```

### consent_definitions

```sql
consent_definitions
  id           UUID PK
  club_id      UUID FK → clubs.id  NOT NULL
  consent_key  VARCHAR(100) NOT NULL
  version      INT NOT NULL DEFAULT 1
  title        VARCHAR(200) NOT NULL
  text_content TEXT NOT NULL
  is_required  BOOLEAN DEFAULT TRUE
  valid_from   TIMESTAMPTZ DEFAULT now()
  valid_until  TIMESTAMPTZ
  created_by   UUID FK → users.id
  created_at   TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, id)   -- composite FK desteği
  UNIQUE: (club_id, consent_key, version)
  INDEX: (club_id, consent_key, valid_from)
```

### consent_events
> **Immutable** — DB trigger UPDATE/DELETE'i engeller.  
> `recorded_at` DB trigger tarafından yazılır; API payload'ında bulunmaz.
>
> **Zaman semantiği:**
> - `effective_at`: hukuki/iş yürürlük zamanı — geçmişe dönük giriş mümkün, API'den alınır
> - `recorded_at`: immutable sistem kayıt zamanı — **DB trigger tarafından yazar**, API değeri yok sayılır
>
> **Mevcut durum sorgusu:**
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
  definition_id         UUID NOT NULL

  event_type            VARCHAR(20) NOT NULL
    CHECK IN ('verildi','reddedildi','geri_alindi','superseded','expired')

  supersedes_event_id   UUID NULL

  -- Zaman
  effective_at          TIMESTAMPTZ NOT NULL DEFAULT now()
    -- Hukuki yürürlük zamanı; API'den alınır; geçmiş tarih kabul edilir
  recorded_at           TIMESTAMPTZ NOT NULL
    -- DB trigger tarafından clock_timestamp() ile doldurulur
    -- API payload'ında BULUNMAMALI; Pydantic şeması bu alanı kabul etmez

  performed_by          UUID FK → users.id
  ip_address            INET
  user_agent            VARCHAR(500)
  channel               VARCHAR(50) CHECK IN ('web','pdf_imza','yazili_form','telefon','mobil')
  document_ref          VARCHAR(500)
  notes                 TEXT

  -- Composite FK desteği
  UNIQUE: (club_id, id)

  -- Tenant-safe FK: definition aynı kulüpte
  CONSTRAINT fk_consent_events_definition_club
    FOREIGN KEY (club_id, definition_id)
    REFERENCES consent_definitions (club_id, id)

  -- Tenant-safe FK: person aynı kulüpte
  CONSTRAINT fk_consent_events_person_club
    FOREIGN KEY (club_id, person_id)
    REFERENCES persons (club_id, id)

  -- Tenant-safe self-ref FK: supersedes event aynı kulüpte
  CONSTRAINT fk_consent_events_supersedes_club
    FOREIGN KEY (club_id, supersedes_event_id)
    REFERENCES consent_events (club_id, id)

  -- İş kuralı: superseded → id zorunlu; diğerleri → id NULL
  CONSTRAINT chk_supersedes_consistency CHECK (
    (event_type = 'superseded' AND supersedes_event_id IS NOT NULL)
    OR
    (event_type <> 'superseded' AND supersedes_event_id IS NULL)
  )

  -- DB garantisi: event kendisini supersede edemez
  CONSTRAINT chk_consent_not_self_supersede CHECK (
    supersedes_event_id IS NULL
    OR supersedes_event_id <> id
  )

  INDEX: (club_id, person_id, definition_id, effective_at DESC)
  INDEX: (club_id, person_id, event_type, effective_at DESC)
  INDEX: (club_id, recorded_at)
```

### person_documents

```sql
person_documents
  id               UUID PK
  club_id          UUID FK → clubs.id  NOT NULL
  person_id        UUID NOT NULL
  document_type    VARCHAR(100) NOT NULL
  storage_provider VARCHAR(50) DEFAULT 'local'
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

### disciplines / boat_classes

```sql
disciplines
  id UUID PK, club_id UUID NULL FK → clubs.id, name VARCHAR(100) NOT NULL,
  code VARCHAR(20), is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT now()
  UNIQUE(club_id, code) WHERE club_id IS NOT NULL
  UNIQUE(code) WHERE club_id IS NULL

boat_classes
  id UUID PK, club_id UUID NULL FK → clubs.id, name VARCHAR(100) NOT NULL,
  code VARCHAR(20), crew_size INT DEFAULT 1, min_age INT, max_age INT,
  discipline_id UUID FK → disciplines.id, is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now()
  UNIQUE(club_id, code) WHERE club_id IS NOT NULL
  UNIQUE(code) WHERE club_id IS NULL
```

---

## DB Trigger'ları (Migration 0005)

```sql
-- ─────────────────────────────────────────────────────────────
-- 1. recorded_at: API değerini yok say, gerçek DB zamanını yaz
-- ─────────────────────────────────────────────────────────────
CREATE FUNCTION set_consent_recorded_at()
RETURNS trigger AS $$
BEGIN
  NEW.recorded_at := clock_timestamp();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_consent_recorded_at
BEFORE INSERT ON consent_events
FOR EACH ROW
EXECUTE FUNCTION set_consent_recorded_at();

-- ─────────────────────────────────────────────────────────────
-- 2. Immutability: UPDATE ve DELETE engelleme
-- ─────────────────────────────────────────────────────────────
CREATE FUNCTION prevent_consent_event_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION
    'consent_events tablosu immutable''dır. Kayıt: %', OLD.id
    USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_consent_events_no_update
BEFORE UPDATE ON consent_events
FOR EACH ROW
EXECUTE FUNCTION prevent_consent_event_mutation();

CREATE TRIGGER trg_consent_events_no_delete
BEFORE DELETE ON consent_events
FOR EACH ROW
EXECUTE FUNCTION prevent_consent_event_mutation();
```

---

## TC Kimlik Şifreleme — Application-Layer AES-256-GCM + AAD

> **pgcrypto KULLANILMAZ.** Şifreleme Python `cryptography.AESGCM` ile yapılır.  
> AAD bağlamı sayesinde ciphertext başka kişi veya kulüp satırına taşınırsa authentication tag doğrulaması başarısız olur.

```python
# backend/app/core/tc_identity.py
import hashlib, hmac as _hmac, os
from uuid import UUID
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# settings.tc_enc_keys: Dict[int, bytes]  — {version: 32-byte-key}
# settings.tc_hmac_key: bytes             — 32-byte

def _aad(club_id: UUID, person_id: UUID, key_version: int) -> bytes:
    """
    AAD kriptografik bağlamı: ciphertext yanlış satıra taşınırsa decrypt başarısız.
    club_id ve person_id dışarıdan değiştirilemez.
    """
    return f"{club_id}:{person_id}:{key_version}".encode()

def encrypt_tc(tc_no: str, club_id: UUID, person_id: UUID, key_version: int) -> bytes:
    """AES-256-GCM + AAD. Çıktı: nonce(12B) || ciphertext."""
    key = settings.tc_enc_keys[key_version]
    nonce = os.urandom(12)
    aad = _aad(club_id, person_id, key_version)
    return nonce + AESGCM(key).encrypt(nonce, tc_no.encode(), aad)

def decrypt_tc(blob: bytes, club_id: UUID, person_id: UUID, key_version: int) -> str:
    """
    Çöz. AAD uyuşmazlığında InvalidTag hatası fırlatır.
    Sonuç asla loglanmaz, cache'lenmez, API response'a eklenmez.
    """
    key = settings.tc_enc_keys[key_version]
    aad = _aad(club_id, person_id, key_version)
    return AESGCM(key).decrypt(blob[:12], blob[12:], aad).decode()

def hmac_tc(tc_no: str) -> str:
    """HMAC-SHA256 hex — arama ve unique constraint."""
    return _hmac.new(settings.tc_hmac_key, tc_no.encode(), hashlib.sha256).hexdigest()
```

### Anahtar Rotasyonu

```
1. Yeni anahtar (v2) env/secret manager'a eklenir.
2. settings.TC_ENC_KEY_ACTIVE_VERSION = 2 yapılır.
3. Yeni kayıtlar v2 + doğru club_id/person_id AAD ile şifrelenir.
4. Arka plan job'ı:
     SELECT id, club_id, person_id, tc_identity_enc, tc_identity_key_version
     FROM persons WHERE tc_identity_key_version < 2
     batch(100):
       plain = decrypt_tc(enc, club_id, person_id, version=1)
       new_enc = encrypt_tc(plain, club_id, person_id, key_version=2)
       UPDATE persons SET tc_identity_enc=new_enc, tc_identity_key_version=2
5. Tüm satırlar taşınana kadar v1 anahtarı SAKLANIR.
6. Tüm satırlar taşındıktan sonra v1 silinir; migration CHECK constraint ekler.
```

---

## ER Diyagramı

```
════════════════════════════════════════════════════════════
AUTH SİSTEMİ (Aşama 2 — mevcut)
════════════════════════════════════════════════════════════
clubs ──< users (.role, .person_id composite FK)
           │
════════════════════════════════════════════════════════════
İŞ ALANI MODELİ (Sprint 3.1)
════════════════════════════════════════════════════════════
clubs ──< persons (.tc_identity_enc+AAD, .tc_identity_key_version)
           │
           ├──< person_capacities (kurumsal görev)
           ├──< memberships
           ├──< athletes ──< person_licenses
           ├──< coaches  ──< person_licenses
           ├──< guardians >── persons
           ├──< coach_athlete_assignments >── persons
           ├──< contact_information
           ├──< addresses
           ├──< emergency_contacts
           ├──< consent_events ──> consent_definitions
           │      ├── CHECK: type=superseded → supersedes_id NOT NULL
           │      ├── CHECK: supersedes_id <> id
           │      ├── TRIGGER: recorded_at = clock_timestamp()
           │      └── TRIGGER: UPDATE/DELETE → RAISE EXCEPTION
           └──< person_documents
```

---

## API Endpoint Listesi

```
GET/POST       /api/v1/persons
GET/PATCH/DEL  /api/v1/persons/{id}
GET            /api/v1/persons/{id}/tc-identity   (kulup_yonetici)

GET/POST       /api/v1/memberships
GET/PATCH      /api/v1/memberships/{id}

GET/POST/GET/PATCH     /api/v1/athletes/{id?}
GET/POST/GET/PATCH     /api/v1/coaches/{id?}
GET/POST/DEL           /api/v1/guardians/{id?}
GET/POST/DEL           /api/v1/coach-assignments/{id?}

GET/POST/PATCH/DEL     /api/v1/persons/{id}/licenses/{lid?}
GET/POST/PATCH/DEL     /api/v1/persons/{id}/contacts/{cid?}
GET/POST/PATCH/DEL     /api/v1/persons/{id}/addresses/{aid?}

GET    /api/v1/persons/{id}/consents          (son durum)
GET    /api/v1/persons/{id}/consents/history  (tüm olaylar)
POST   /api/v1/persons/{id}/consents

GET/POST/GET/DEL       /api/v1/persons/{id}/documents/{did?}

GET    /api/v1/disciplines
GET    /api/v1/boat-classes
```

---

## RBAC Matrisi

| Endpoint | kulup_yonetici | antrenor | muhasebe | sporcu | veli | misafir |
|---|---|---|---|---|---|---|
| GET /persons | ✅ tüm | ✅ atanmış | ✅ finansal | ✅ kendin | ✅ çocuk | ❌ |
| POST/DELETE /persons | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /tc-identity | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /memberships | ✅ | ✅ | ✅ | ✅ kendi | ✅ çocuk | ❌ |
| GET /athletes | ✅ | ✅ atanmış | ❌ | ✅ kendi | ✅ çocuk | ❌ |
| POST /coach-assignments | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET/POST /consents | ✅ | ❌ | ❌ | ✅ kendi | ✅ kendi+çocuk | ❌ |
| GET /documents | ✅ | ✅ lisans/sigorta | ❌ | ✅ kendi | ✅ çocuk | ❌ |

> Yanlış kulüp → **404**. `assert_same_club()` tüm endpoint'lerde yetki kontrolünden önce.

---

## Kişisel Veri Sınıflandırması

| Alan | KVKK | Şifreleme | Erişim |
|---|---|---|---|
| `tc_identity_enc` | ÖZEL — Kimlik | App-layer AES-256-GCM + AAD | Sadece `kulup_yonetici` |
| `tc_identity_hmac` | Türetilmiş | HMAC-SHA256 | DB; API'de okunmaz |
| `tc_identity_key_version` | Teknik | — | Rotasyon job'ı |
| `date_of_birth` | KİŞİSEL | Yok | Yönetici, antrenör, kendi |
| Consent olayları | KVKK | Yok | Yönetici + kendi |
| Finansal (3.4) | KİŞİSEL | Yok | Yönetici + muhasebe |

---

## Migration Planı

```
0002_persons_core.py
  + persons (UNIQUE(club_id,id), tc_identity_key_version)
  + ALTER TABLE users ADD person_id + composite FK

0003_persons_roles_memberships.py
  + person_capacities, memberships, athletes, coaches,
    guardians, coach_athlete_assignments

0004_persons_licenses_contacts.py
  + person_licenses, contact_information, addresses, emergency_contacts

0005_consent_events.py
  + consent_definitions (UNIQUE(club_id,id))
  + consent_events (UNIQUE(club_id,id), composite FK'lar,
                    effective_at, recorded_at,
                    chk_supersedes_consistency,
                    chk_consent_not_self_supersede)
  + FUNCTION set_consent_recorded_at()
  + TRIGGER trg_consent_recorded_at (BEFORE INSERT)
  + FUNCTION prevent_consent_event_mutation()
  + TRIGGER trg_consent_events_no_update (BEFORE UPDATE)
  + TRIGGER trg_consent_events_no_delete (BEFORE DELETE)

0006_person_documents.py
  + person_documents

0007_reference_tables.py
  + disciplines, boat_classes, seed verileri
```

`IF NOT EXISTS` kullanılmaz. `alembic heads` → tek head.

---

## Test Planı

### Birim Testleri

**`test_persons.py`**
- CRUD tam döngü
- Tenant izolasyonu: kulüp B token'ı → kulüp A kişisi → 404
- Composite FK: farklı club_id kombinasyonu → DB constraint hatası
- TC: kaydet → oku → çöz → eşleşir; düz metin DB'de yok
- TC AAD: aynı ciphertext farklı person_id ile decrypt → `InvalidTag` hatası
- TC AAD: aynı ciphertext farklı club_id ile decrypt → `InvalidTag` hatası
- TC AAD: yanlış key_version ile decrypt → `InvalidTag` hatası
- TC HMAC: aynı TC → aynı HMAC; farklı TC → farklı HMAC
- Duplicate TC (aynı kulüp) → unique constraint hatası
- Key version: yeni kayıt aktif version ile şifrelenir
- Key version: eski version ile şifrenlenmiş eski kayıt okunabilir

**`test_memberships.py`**
- Üyelik no otomatik artan; iptal sonrası aynı no → unique violation
- `start_date > end_date` → 422

**`test_athletes.py` / `test_coaches.py`**
- Kişisiz profil → 422; aynı kişiye 2. profil → 409

**`test_guardians.py`**
- `guardian_person_id == athlete_person_id` → 422
- Başkasının çocuğu → 404

**`test_coach_assignments.py`**
- Atanmış sporcu görünür; atanmamış → 404; çakışan aktif → 409

**`test_consents.py`**
- Olay immutable: önceki kayıt değişmez
- Son durum `effective_at DESC` sıralamasıyla belirlenir
- Geçmişe dönük `effective_at` → sıralama doğru
- `recorded_at` API payload'ında gönderilirse → 422 (Pydantic şeması reddeder)
- DB INSERT ile özel `recorded_at` gönderilse bile trigger `clock_timestamp()` yazar
- `id = supersedes_event_id` → CHECK constraint hatası
- `superseded` event tipinde `supersedes_event_id = NULL` → CHECK hatası
- `superseded` dışı tipte `supersedes_event_id` dolu → CHECK hatası
- UPDATE consent_events → DB `restrict_violation` hatası
- DELETE consent_events → DB `restrict_violation` hatası
- Başka kişiye ait (aynı tenant) event supersede → service 422
- Başka definition zincirine ait event supersede → service 422
- Cross-tenant definition FK → DB composite FK hatası

**`test_person_licenses.py`**
- Farklı tipte N lisans → OK; süresi dolmuş → `is_active=False`

### Entegrasyon Testleri (Docker)

- TC şifreleme uçtan uca (API container'ında Python AESGCM + AAD)
- Composite FK: farklı kulüpten persons FK → DB constraint hatası
- `trg_consent_recorded_at`: INSERT sırasında `recorded_at` triggerden geliyor
- `trg_consent_events_no_update`: UPDATE → DB exception
- `trg_consent_events_no_delete`: DELETE → DB exception
- `s3_0a_verify.sh` kriter 30: çapraz tenant → 404

---

## Servis Katmanı Kuralları (`ConsentService.supersede()`)

DB CHECK'leri satır düzeyinde çalışır; çapraz satır doğrulaması servis katmanında yapılır:

```python
async def supersede(self, club_id, person_id, supersedes_event_id, ...):
    # 1. Hedef event'i yükle
    target = await self.repo.get_event(supersedes_event_id)
    if target is None:
        raise NotFoundError()
    # 2. Aynı tenant (composite FK zaten engeller ama erken hata iyidir)
    if target.club_id != club_id:
        raise ForbiddenError()
    # 3. Aynı kişi
    if target.person_id != person_id:
        raise UnprocessableError("Başka kişiye ait event supersede edilemez")
    # 4. Aynı definition zinciri (consent_key eşleşmeli)
    target_def = await self.repo.get_definition(target.definition_id)
    new_def = await self.repo.get_definition(new_definition_id)
    if target_def.consent_key != new_def.consent_key:
        raise UnprocessableError("Farklı consent key zincirindeki event supersede edilemez")
    # 5. Kendisini supersede etme — DB CHECK zaten yakalar; burada da erken hata:
    if supersedes_event_id == new_event_id:
        raise UnprocessableError("Event kendisini supersede edemez")
```

---

## Başlamadan Önce Beklenecek

1. `s3_0a_verify.sh` → exit 0 veya exit 2 (0 FAIL)
2. `sprint3_0a_run.log` kaydedilmiş
3. **Bu REV4 FINAL planı onaylandı**

> Kodlamaya başlamadan önce: `0002_persons_core.py` migration → `alembic upgrade head` test → model → endpoint → test sırası.

---

## Gelecek Sprint'ler İçin Açık Kararlar

**DDD Mimarisi** — Sprint 4 öncesi karar (Sprint 3.3 retrospektifinde).  
**boat_class_disciplines N:N** — Sprint 3.2/3.3.  
**person_documents scan_status** — Sprint 3.6.  
**Performans testleri** — Sprint 3.1 sonrası (k6/Locust, 5K persons, 500 eş zamanlı).

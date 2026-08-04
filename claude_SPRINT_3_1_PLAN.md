# Sprint 3.1 — Temel Kişi ve Üyelik Mimarisi

**Durum:** BEKLEME — Sprint 3.0-A tam PASS olduktan sonra başlanacak  
**Önkoşul:** SPRINT_3_0_A_INTEGRATION_REPORT.md → tüm 30 kriter PASS

---

## Kapsam

Tüm iş modüllerinin temelini oluşturan kişi–üyelik–rol veri modeli.  
Sporcu, veli, antrenör, muhasebe, çalışan için **ayrı kişi tablosu yok**;  
merkezi `persons` tablosu, role göre genişleme stratejisi.

---

## Tablolar (12 tablo + 2 junction)

### Çekirdek Kişi

```
persons
  id              UUID PK
  club_id         UUID FK → clubs.id   (tenant)
  first_name      VARCHAR(100) NOT NULL
  last_name       VARCHAR(100) NOT NULL
  date_of_birth   DATE
  gender          VARCHAR(10)  CHECK IN ('erkek','kadin','diger','belirtilmedi')
  tc_identity     BYTEA        (pgcrypto AES-256 — Sprint 3.2)
  nationality     VARCHAR(3)   DEFAULT 'TR'
  profile_photo   VARCHAR(500)
  notes           TEXT
  is_active       BOOLEAN DEFAULT TRUE
  is_deleted      BOOLEAN DEFAULT FALSE
  deleted_at      TIMESTAMPTZ
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, is_deleted)
  INDEX: (club_id, last_name, first_name)
```

### Üyelik

```
memberships
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id
  membership_no   VARCHAR(50) UNIQUE per club   (generated: MYK-2024-0001)
  membership_type VARCHAR(50)  CHECK IN ('sporcu','veli','onursal','personel','misafir')
  status          VARCHAR(20)  CHECK IN ('aktif','pasif','askida','iptal')
  start_date      DATE NOT NULL
  end_date        DATE
  renewal_date    DATE
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, membership_no)
  INDEX: (club_id, status)
  INDEX: (club_id, person_id)
```

### Rol Atamaları

```
person_roles
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id
  role            VARCHAR(50)  (kulup_yonetici, antrenor, muhasebe, sporcu, veli, misafir...)
  is_primary      BOOLEAN DEFAULT FALSE
  assigned_at     TIMESTAMPTZ DEFAULT now()
  assigned_by     UUID FK → users.id
  revoked_at      TIMESTAMPTZ
  notes           TEXT

  INDEX: (club_id, person_id, role)
  INDEX: (club_id, role, revoked_at) WHERE revoked_at IS NULL
```

### Sporcu Profili

```
athletes
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id  UNIQUE per club
  license_no      VARCHAR(100)
  license_expires DATE
  federation      VARCHAR(100)  DEFAULT 'TYF'
  boat_class      VARCHAR(100)  (Optimist, Laser, 420, 470, RS:X...)
  competition_level VARCHAR(50) (yerel, ulusal, uluslararasi)
  tyf_registered  BOOLEAN DEFAULT FALSE
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, person_id)
  INDEX: (club_id, license_no)
```

### Veli / Vasi İlişkisi

```
guardians
  id              UUID PK
  club_id         UUID FK → clubs.id
  guardian_person_id UUID FK → persons.id
  athlete_person_id  UUID FK → persons.id
  relation_type   VARCHAR(50)  CHECK IN ('anne','baba','vasi','diger')
  is_primary      BOOLEAN DEFAULT FALSE
  emergency_priority INT DEFAULT 0
  created_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, guardian_person_id, athlete_person_id)
  INDEX: (club_id, athlete_person_id)
```

### Antrenör Profili

```
coaches
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id  UNIQUE per club
  license_no      VARCHAR(100)
  license_level   VARCHAR(50)   (Seviye 1, 2, 3, Milli Takım...)
  license_expires DATE
  specializations TEXT[]        (Optimist, Match Racing, Teknik...)
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE: (club_id, person_id)
```

### İletişim Bilgileri

```
contact_information
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id
  contact_type    VARCHAR(30)  CHECK IN ('telefon','email','adres','sosyal')
  label           VARCHAR(50)  ('ev','is','mobil','kisisel','veli' ...)
  value           VARCHAR(500) NOT NULL
  is_primary      BOOLEAN DEFAULT FALSE
  is_verified     BOOLEAN DEFAULT FALSE
  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, contact_type)
```

### Adresler

```
addresses
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id
  label           VARCHAR(50)   ('ev','is','...)
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

### Acil Durum Kişileri

```
emergency_contacts
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id  (asıl kişi)
  contact_name    VARCHAR(200) NOT NULL
  relation        VARCHAR(100)
  phone           VARCHAR(50)  NOT NULL
  phone_alt       VARCHAR(50)
  priority        INT DEFAULT 1
  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, priority)
```

### KVKK / Onay Kayıtları

```
consents
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id
  consent_type    VARCHAR(100)  (kvkk_acik_riza, saglik_bilgisi, fotograf_yayini...)
  status          VARCHAR(20)   CHECK IN ('verildi','reddedildi','geri_alindi')
  given_at        TIMESTAMPTZ
  expires_at      TIMESTAMPTZ
  given_by        UUID FK → users.id
  document_ref    VARCHAR(500)  (imzalı form path)
  ip_address      INET
  notes           TEXT
  created_at      TIMESTAMPTZ DEFAULT now()

  INDEX: (club_id, person_id, consent_type)
  INDEX: (club_id, consent_type, status)
```

### Kişi Belgeleri (metadata)

```
person_documents
  id              UUID PK
  club_id         UUID FK → clubs.id
  person_id       UUID FK → persons.id
  document_type   VARCHAR(100)  (kimlik, lisans, sigorta, saglik_raporu, veli_izni...)
  file_path       VARCHAR(500)
  file_name       VARCHAR(200)
  mime_type       VARCHAR(100)
  file_size       INT
  valid_from      DATE
  valid_until     DATE
  issued_by       VARCHAR(200)
  uploaded_by     UUID FK → users.id
  uploaded_at     TIMESTAMPTZ DEFAULT now()
  is_verified     BOOLEAN DEFAULT FALSE
  verified_by     UUID FK → users.id
  notes           TEXT

  INDEX: (club_id, person_id, document_type)
  INDEX: (club_id, valid_until) WHERE valid_until IS NOT NULL
```

---

## RBAC Matrisi

| Endpoint | kulup_yonetici | antrenor | muhasebe | sporcu | veli | misafir |
|---|---|---|---|---|---|---|
| GET /persons | ✅ kendi kulübü | ✅ atanmış sporcular | ✅ finansal profil | ✅ sadece kendin | ✅ sadece çocuk | ❌ |
| POST /persons | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| PATCH /persons/{id} | ✅ | ✅ antrenman notu | ❌ | ✅ kendi profili | ✅ veli bilgisi | ❌ |
| DELETE /persons/{id} | ✅ soft delete | ❌ | ❌ | ❌ | ❌ | ❌ |
| GET /memberships | ✅ | ✅ | ✅ | ✅ kendi | ✅ çocuk | ❌ |
| GET /athletes | ✅ | ✅ | ❌ | ✅ kendi | ✅ çocuk | ❌ |
| GET /consents | ✅ | ❌ | ❌ | ✅ kendi | ✅ kendi+çocuk | ❌ |
| GET /person_documents | ✅ | ✅ lisans/sigorta | ❌ | ✅ kendi | ✅ çocuk | ❌ |

---

## Kişisel Veri Sınıflandırması

| Alan | Kategori | Şifreleme | Erişim |
|---|---|---|---|
| tc_identity | ÖZEL — Kimlik | AES-256 pgcrypto (Sprint 3.2) | Sadece kulup_yonetici |
| date_of_birth | KİŞİSEL | Yok (erişim kontrolü) | Yönetici, antrenör, kendi |
| health_data (Sprint 3.2) | ÖZEL — Sağlık | AES-256 | Yönetici + onaylı antrenör |
| contact phone/email | KİŞİSEL | Yok | Yönetici, kendi |
| profile_photo | KİŞİSEL | Yok | Herkese açık veya kulüp içi |
| consents | KVKK | Yok (log) | Yönetici + kendi |

---

## API Endpoint Listesi

```
# Kişiler
GET    /api/v1/persons                    (filtreleme: club, rol, aktif, arama)
POST   /api/v1/persons
GET    /api/v1/persons/{id}
PATCH  /api/v1/persons/{id}
DELETE /api/v1/persons/{id}              (soft delete)

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

# İletişim
GET    /api/v1/persons/{id}/contacts
POST   /api/v1/persons/{id}/contacts
PATCH  /api/v1/persons/{id}/contacts/{contact_id}
DELETE /api/v1/persons/{id}/contacts/{contact_id}

# Onaylar / KVKK
GET    /api/v1/persons/{id}/consents
POST   /api/v1/persons/{id}/consents
PATCH  /api/v1/persons/{id}/consents/{consent_id}   (geri alma)

# Belgeler
GET    /api/v1/persons/{id}/documents
POST   /api/v1/persons/{id}/documents               (upload)
GET    /api/v1/persons/{id}/documents/{doc_id}
DELETE /api/v1/persons/{id}/documents/{doc_id}
```

---

## Migration Planı

```
0002_persons_and_membership.py
  - persons
  - memberships
  - person_roles
  - athletes
  - guardians
  - coaches
  - contact_information
  - addresses
  - emergency_contacts
  - consents
  - person_documents
  + index'ler
  + soft delete trigger (updated_at)
```

---

## Test Planı

### Birim Testleri (`test_persons.py`, `test_memberships.py`)
- Kişi CRUD: oluştur, listele, güncelle, soft delete
- Tenant izolasyonu: kulüp A, kulüp B karışmaz
- RBAC: yönetici tüm kişileri görür, sporcu sadece kendini
- Soft delete: silinmiş kayıt listede görünmez, ayrı endpoint ile erişilebilir
- Veli–sporcu ilişkisi: veli çocuk profilini görür, başkasını göremez
- Antrenör: atanmış sporcu listesini görür (atanmamışları göremez)

### Entegrasyon Testleri
- Üyelik numarası otomatik sıralı oluşuyor
- Lisans geçerlilik tarihi geçmiş → uyarı/flag
- Belge geçerlilik bitiş → bildirim hook (Sprint 3.7)
- Consent revoke → audit log

---

## Başlamadan Önce Beklenecek

1. `SPRINT_3_0_A_INTEGRATION_REPORT.md` → tüm 30 kriter PASS
2. `s3_0a_verify.sh` çıktısı `sprint3_0a_run.log` kaydedilmiş
3. Bu plan onaylandı

> Sprint 3.1 uygulaması bu plan onaylandıktan sonra başlar.

# MYK Platform V2 — Önerilen Veri Modeli
**Faz 1 Çıktısı · 2026-07-30**

---

## 1. Tasarım Prensipleri

- **Multi-tenant:** Her kayıt `club_id` (UUID) taşır; satır seviyesinde izolasyon
- **Soft-delete:** Hiçbir kayıt fiziksel silinmez; `is_deleted + deleted_at`
- **Audit izlenebilirliği:** Tüm değiştirici işlemler `audit_log` tablosuna yazılır
- **Şifreli hassas alanlar:** `tc_no`, `kan_grubu`, `alerji`, `ozel_durum` → PostgreSQL `pgcrypto` ile şifreli
- **RBAC:** `roles` + `role_permissions` + `user_permissions` üç katmanlı
- **Zaman damgaları:** Tüm tablolarda `created_at`, `updated_at` (UTC)
- **UUID:** Tüm birincil anahtarlar UUID v4

---

## 2. Temel Varlıklar

### 2.1 Tenant & Kimlik

```sql
clubs (
  id             UUID PK,
  slug           VARCHAR(50) UNIQUE,    -- URL identifier
  name           VARCHAR(200),
  plan           VARCHAR(20),           -- free | pro | enterprise
  is_active      BOOLEAN DEFAULT true,
  settings       JSONB,                 -- kulüp-özel yapılandırma
  created_at     TIMESTAMPTZ,
  updated_at     TIMESTAMPTZ
)

users (
  id             UUID PK,
  club_id        UUID FK → clubs,
  email          VARCHAR(255),
  password_hash  VARCHAR(255),          -- Argon2id
  full_name      VARCHAR(200),
  role           VARCHAR(30),           -- FK → roles.name
  is_active      BOOLEAN DEFAULT true,
  mfa_secret     VARCHAR(100),          -- TOTP (Phase 2, nullable)
  last_login_at  TIMESTAMPTZ,
  is_deleted     BOOLEAN DEFAULT false,
  created_at     TIMESTAMPTZ,
  updated_at     TIMESTAMPTZ,
  UNIQUE(club_id, email)
)

roles (
  name           VARCHAR(30) PK,        -- yonetici | muhasebe | antrenor | ...
  description    VARCHAR(500),
  is_system      BOOLEAN DEFAULT true
)

role_permissions (
  role           VARCHAR(30) FK → roles,
  permission     VARCHAR(100),          -- sporcu:read | belge:* | vs.
  PRIMARY KEY(role, permission)
)

user_permissions (
  user_id        UUID FK → users,
  permission     VARCHAR(100),
  granted        BOOLEAN,               -- true = grant, false = deny
  granted_by     UUID FK → users,
  PRIMARY KEY(user_id, permission)
)

refresh_tokens (
  id             UUID PK,
  user_id        UUID FK → users,
  token_hash     VARCHAR(255),
  expires_at     TIMESTAMPTZ,
  revoked_at     TIMESTAMPTZ,
  created_at     TIMESTAMPTZ
)
```

### 2.2 Sporcu & Üye

```sql
athletes (
  id                   UUID PK,
  club_id              UUID FK → clubs,
  user_id              UUID FK → users (nullable),  -- kulüp hesabı varsa
  full_name            VARCHAR(200),
  birth_date           DATE,
  tc_no_encrypted      BYTEA,           -- pgcrypto şifreli
  kan_grubu_encrypted  BYTEA,           -- pgcrypto şifreli
  alerji_encrypted     BYTEA,           -- pgcrypto şifreli
  ozel_durum_encrypted BYTEA,           -- pgcrypto şifreli
  emergency_contact    VARCHAR(200),
  emergency_phone      VARCHAR(20),     -- şifreli
  license_no           VARCHAR(50),
  license_expires      DATE,
  health_cert_expires  DATE,
  is_deleted           BOOLEAN DEFAULT false,
  created_at           TIMESTAMPTZ,
  updated_at           TIMESTAMPTZ
)

guardian_athlete (
  guardian_id    UUID FK → users,
  athlete_id     UUID FK → athletes,
  club_id        UUID FK → clubs,
  PRIMARY KEY(guardian_id, athlete_id)
)
```

### 2.3 Eğitim

```sql
courses (
  id             UUID PK,
  club_id        UUID FK → clubs,
  name           VARCHAR(200),
  level          VARCHAR(50),           -- D1 | D2 | D3 | US1 | vs.
  instructor_id  UUID FK → users,
  start_date     DATE,
  end_date       DATE,
  capacity       INTEGER,
  fee            NUMERIC(10,2),
  is_active      BOOLEAN DEFAULT true,
  created_at     TIMESTAMPTZ,
  updated_at     TIMESTAMPTZ
)

enrollments (
  id             UUID PK,
  club_id        UUID FK → clubs,
  course_id      UUID FK → courses,
  athlete_id     UUID FK → athletes,
  enrolled_at    TIMESTAMPTZ,
  status         VARCHAR(20),           -- active | completed | dropped
  created_at     TIMESTAMPTZ
)

attendance (
  id             UUID PK,
  club_id        UUID FK → clubs,
  course_id      UUID FK → courses,
  athlete_id     UUID FK → athletes,
  date           DATE,
  present        BOOLEAN,
  note           VARCHAR(500),
  recorded_by    UUID FK → users,
  created_at     TIMESTAMPTZ
)

payments (
  id             UUID PK,
  club_id        UUID FK → clubs,
  enrollment_id  UUID FK → enrollments (nullable),
  user_id        UUID FK → users,
  amount         NUMERIC(10,2),
  currency       VARCHAR(3) DEFAULT 'TRY',
  status         VARCHAR(20),           -- pending | paid | overdue | refunded
  due_date       DATE,
  paid_at        TIMESTAMPTZ,
  created_at     TIMESTAMPTZ
)
```

### 2.4 Akademi (KnotPlayer)

```sql
knot_types (
  id             UUID PK,
  club_id        UUID FK → clubs,
  slug           VARCHAR(100) UNIQUE,   -- izbarco, cifte-gerekli, vs.
  name           VARCHAR(200),
  description    TEXT,
  timeline_path  VARCHAR(500),          -- static dosya yolu
  is_active      BOOLEAN DEFAULT true,
  created_at     TIMESTAMPTZ
)

academy_progress (
  id             UUID PK,
  club_id        UUID FK → clubs,
  user_id        UUID FK → users,
  knot_slug      VARCHAR(100),
  step_number    INTEGER,
  total_steps    INTEGER,
  completed_at   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ,
  UNIQUE(club_id, user_id, knot_slug)
)
```

### 2.5 Doküman Yönetimi

```sql
documents (
  id              UUID PK,
  club_id         UUID FK → clubs,
  doc_code        VARCHAR(100),
  title           VARCHAR(500),
  category        VARCHAR(100),
  doc_type        VARCHAR(50),
  revision        VARCHAR(20),
  status          VARCHAR(30),          -- active | superseded | archived | conflict
  conflict_code   VARCHAR(50),          -- CONFLICT-001 gibi
  source_authority VARCHAR(100),        -- MYK-kontrollü | TYF-resmi
  storage_key     VARCHAR(500),         -- object storage path
  mime_type       VARCHAR(100),
  file_size       INTEGER,
  sha256          VARCHAR(64),
  uploaded_by     UUID FK → users,
  is_deleted      BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ
)

document_revisions (
  id              UUID PK,
  document_id     UUID FK → documents,
  club_id         UUID FK → clubs,
  previous_rev_id UUID FK → document_revisions (nullable),
  revision        VARCHAR(20),
  storage_key     VARCHAR(500),
  sha256          VARCHAR(64),
  note            TEXT,
  created_by      UUID FK → users,
  created_at      TIMESTAMPTZ
)
```

### 2.6 Operasyon

```sql
equipment (
  id              UUID PK,
  club_id         UUID FK → clubs,
  name            VARCHAR(200),
  category        VARCHAR(100),
  serial_no       VARCHAR(100),
  status          VARCHAR(30),          -- active | maintenance | retired
  last_maintenance DATE,
  next_maintenance DATE,
  notes           TEXT,
  is_deleted      BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ
)

sea_logs (
  id              UUID PK,
  club_id         UUID FK → clubs,
  date            DATE,
  vessel          VARCHAR(200),
  crew            JSONB,                -- [{user_id, role}]
  departure_time  TIME,
  return_time     TIME,
  weather         VARCHAR(200),
  route           TEXT,
  notes           TEXT,
  logged_by       UUID FK → users,
  created_at      TIMESTAMPTZ
)

reservations (
  id              UUID PK,
  club_id         UUID FK → clubs,
  user_id         UUID FK → users,
  resource_type   VARCHAR(50),          -- equipment | venue
  resource_id     UUID,
  start_at        TIMESTAMPTZ,
  end_at          TIMESTAMPTZ,
  status          VARCHAR(20),          -- pending | confirmed | cancelled
  created_at      TIMESTAMPTZ
)
```

### 2.7 Kalite & İzlenebilirlik

```sql
nonconformities (
  id              UUID PK,
  club_id         UUID FK → clubs,
  title           VARCHAR(500),
  category        VARCHAR(100),
  severity        VARCHAR(20),          -- critical | major | minor
  status          VARCHAR(30),          -- open | in_progress | closed
  reported_by     UUID FK → users,
  assigned_to     UUID FK → users,
  resolved_at     TIMESTAMPTZ,
  description     TEXT,
  corrective_action TEXT,
  created_at      TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ
)

audit_log (
  id              UUID PK,
  club_id         UUID FK → clubs,
  user_id         UUID FK → users,
  action          VARCHAR(100),
  resource_type   VARCHAR(100),
  resource_id     UUID,
  changes         JSONB,                -- {before: {...}, after: {...}}
  ip_address      INET,
  user_agent      VARCHAR(500),
  created_at      TIMESTAMPTZ
)
```

---

## 3. İndeks Stratejisi

```sql
-- Tenant izolasyonu için
CREATE INDEX ON users (club_id);
CREATE INDEX ON athletes (club_id);
CREATE INDEX ON documents (club_id, doc_code);
CREATE INDEX ON audit_log (club_id, created_at DESC);

-- Sık kullanılan filtreler
CREATE INDEX ON athletes (club_id, license_expires);
CREATE INDEX ON payments (club_id, status, due_date);
CREATE INDEX ON attendance (club_id, course_id, date);
CREATE INDEX ON document_revisions (document_id, created_at DESC);
```

---

## 4. SQLite → PostgreSQL Dönüşüm Notu

| SQLite Karşılığı | PostgreSQL V2 Karşılığı |
|---|---|
| INTEGER PK autoincrement | UUID v4 |
| TEXT (JSON blob) | JSONB |
| TEXT (tarih) | DATE / TIMESTAMPTZ |
| BLOB (şifreli) | BYTEA (pgcrypto) |
| Yok | INET (IP adresi) |
| Yok | ENUM'a benzer CHECK constraint |

---

*Bu model mevcut SQLite şeması (9 migration, 16 tablo) ve V2 gereksinim spesifikasyonu temel alınarak tasarlanmıştır.*

# Sprint 6A — Training Core
**Hedef sürüm:** v0.8.0  
**Migration:** `0008_training_core`  
**Kaynak analiz:** `/opt/myk/app.py` DDL (kurslar + kayitlar + yoklama)

---

## Kapsam

Fiziksel yelken eğitimi: kurs yönetimi, katılımcı kaydı, ders oturumları, yoklama ve yoklama raporu.

> **Bu domain Academy'den tamamen ayrıdır.**  
> `training_*` tabloları ↔ `academy_*` tabloları — hiçbir FK ilişkisi yok.

---

## Veri Modeli — PostgreSQL Şeması (`0009_training_core`)

### `training_courses`
Eski tablo: `kurslar`

```sql
CREATE TABLE training_courses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id         UUID NOT NULL REFERENCES clubs(id),
    name            TEXT NOT NULL,
    description     TEXT,
    class_name      TEXT,                    -- eski: sinif
    level           TEXT,                    -- eski: seviye
    start_date      DATE,
    end_date        DATE,
    schedule_text   TEXT,                    -- eski: gun_saatleri (TEXT olarak kalıyor)
    capacity        INTEGER NOT NULL DEFAULT 0,
    fee             NUMERIC(10,2) NOT NULL DEFAULT 0,   -- eski: ucret REAL
    instructor_person_id UUID REFERENCES persons(id),  -- eski: egitmen_id → kullanicilar → persons
    status          TEXT NOT NULL DEFAULT 'planlandi'
                    CHECK (status IN ('planlandi','aktif','tamamlandi','iptal')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_training_courses_club ON training_courses(club_id);
CREATE INDEX ix_training_courses_club_status ON training_courses(club_id, status) WHERE deleted_at IS NULL;
```

**Notlar:**
- `egitmen_id` → `instructor_person_id` (domain kişisi, auth kullanıcısı değil)
- `aktif + silinmis_mi` → `is_active + deleted_at` (soft delete standardı)
- `ucret REAL` → `NUMERIC(10,2)` (para birimi güvenliği)
- `gun_saatleri TEXT` → `schedule_text TEXT` (ilk iterasyonda serbest metin yeterli)

---

### `training_sessions`
Eski sistemde yoktu. Yeni mimari ek: "ders günü" nesnesi.

```sql
CREATE TABLE training_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id         UUID NOT NULL REFERENCES clubs(id),
    course_id       UUID NOT NULL REFERENCES training_courses(id) ON DELETE CASCADE,
    session_date    DATE NOT NULL,
    start_time      TIME,
    end_time        TIME,
    instructor_person_id UUID REFERENCES persons(id),  -- oturuma özel eğitmen (opsiyonel)
    notes           TEXT,
    status          TEXT NOT NULL DEFAULT 'planli'
                    CHECK (status IN ('planli','tamamlandi','iptal')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_training_sessions_course ON training_sessions(course_id);
-- DB-level unique YOK: aynı gün sabah+öğleden sonra, teorik+pratik seans mümkün olmalı.
-- Duplicate kontrolü service katmanında. İleride start_time zorunlu olursa (course_id, session_date, start_time) unique eklenebilir.
CREATE INDEX ix_training_sessions_course_date ON training_sessions(club_id, course_id, session_date);
```

**Notlar:**
- Eski yoklama `tarih + kurs_id` kombinasyonunu bu tablo replace eder
- `session_date` kurs başına unique — aynı gün iki oturum planlanmak istenirse bu kısıtlama kaldırılabilir

---

### `training_enrollments`
Eski tablo: `kayitlar`

```sql
CREATE TABLE training_enrollments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id         UUID NOT NULL REFERENCES clubs(id),
    course_id       UUID NOT NULL REFERENCES training_courses(id),
    person_id       UUID NOT NULL REFERENCES persons(id),   -- eski: sporcu_id
    status          TEXT NOT NULL DEFAULT 'aktif'
                    CHECK (status IN ('aktif','iptal','tamamlandi')),
    payment_status  TEXT NOT NULL DEFAULT 'beklemede'
                    CHECK (payment_status IN ('beklemede','odendi','gecikti')),
    notes           TEXT,
    enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelled_at    TIMESTAMPTZ                              -- eski: silinmis_mi
);

-- PostgreSQL partial unique: aynı kişi aynı kursa aktif olarak sadece bir kez kaydolabilir
CREATE UNIQUE INDEX uq_enrollment_active
    ON training_enrollments(course_id, person_id)
    WHERE cancelled_at IS NULL;

CREATE INDEX ix_training_enrollments_club_person ON training_enrollments(club_id, person_id);
CREATE INDEX ix_training_enrollments_club_course ON training_enrollments(club_id, course_id);
```

**Kritik fark — SQLite vs PostgreSQL unique trick:**  
Eski sistem: `UNIQUE(sporcu_id, kurs_id, silinmis_mi)` → silinmis_mi=0 olan tek kayıt  
Yeni sistem: `PARTIAL UNIQUE WHERE cancelled_at IS NULL` → semantik olarak eşdeğer, daha temiz

**Sprint 6B notu:**  
`payment_status` şimdilik `training_enrollments` üzerinde taşınır.  
Sprint 6B'de `payments` domain source-of-truth olur; bu alan denormalize özet olarak kalabilir veya kaldırılabilir.

---

### `training_attendance`
Eski tablo: `yoklama`

```sql
CREATE TABLE training_attendance (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id         UUID NOT NULL REFERENCES clubs(id),
    session_id      UUID NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
    person_id       UUID NOT NULL REFERENCES persons(id),   -- eski: sporcu_id
    status          TEXT NOT NULL DEFAULT 'var'
                    CHECK (status IN ('var','yok','izinli','gecikti')),  -- kaynak: GECERLI set
    check_in_time   TIME,                                    -- eski: giris_saati
    check_out_time  TIME,                                    -- eski: cikis_saati
    notes           TEXT,
    recorded_by_user_id UUID REFERENCES users(id),          -- eski: olusturan_id → kullanicilar
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_attendance UNIQUE (session_id, person_id)
);

CREATE INDEX ix_training_attendance_session ON training_attendance(session_id);
CREATE INDEX ix_training_attendance_person  ON training_attendance(club_id, person_id);
```

**Notlar:**
- `giris_saati / cikis_saati` korundu — DDL'de mevcuttu
- `UNIQUE (session_id, person_id)` explicit constraint (eski sistemde implicit/upsert logic)
- `olusturan_id` → `recorded_by_user_id` (kim girdi = User, kim katıldı = Person)

---

## Kimlik Ayrımı (Sprint 5C ile tutarlı)

| Alan | Tip | Açıklama |
|------|-----|----------|
| `instructor_person_id` | `UUID → persons` | Eğitmen = domain kişisi |
| `person_id` (enrollment) | `UUID → persons` | Katılımcı = domain kişisi |
| `person_id` (attendance) | `UUID → persons` | Yoklamaya giren kişi |
| `recorded_by_user_id` | `UUID → users` | İşlemi yapan auth kullanıcısı |

---

## API Sözleşmesi

### Kurslar

```
GET    /api/v1/trainings
       Query: status, active_only (default: true)
       Response: TrainingCourseList

POST   /api/v1/trainings
       Body: TrainingCourseCreate
       Response: TrainingCourseOut

GET    /api/v1/trainings/{course_id}
       Response: TrainingCourseDetail (+ enrollment_count, sessions)

PATCH  /api/v1/trainings/{course_id}
       Body: TrainingCourseUpdate (partial)
       Response: TrainingCourseOut

DELETE /api/v1/trainings/{course_id}
       → soft delete: deleted_at = now()
```

### Katılımcılar

```
GET    /api/v1/trainings/{course_id}/participants
       Response: TrainingEnrollmentList

POST   /api/v1/trainings/{course_id}/participants
       Body: { person_id: UUID, notes?: str }
       Kural: kapasite kontrol + duplicate aktif kayıt kontrol
       Response: TrainingEnrollmentOut

DELETE /api/v1/trainings/{course_id}/participants/{person_id}
       → cancelled_at = now(), status = 'iptal'
```

### Oturumlar

```
GET    /api/v1/trainings/{course_id}/sessions
       Response: TrainingSessionList

POST   /api/v1/trainings/{course_id}/sessions
       Body: TrainingSessionCreate
       Response: TrainingSessionOut

PATCH  /api/v1/trainings/{course_id}/sessions/{session_id}
       Body: TrainingSessionUpdate
       Response: TrainingSessionOut
```

### Yoklama

```
GET    /api/v1/trainings/{course_id}/sessions/{session_id}/attendance
       Response: list[TrainingAttendanceOut]
       İçerir: kurs katılımcıları (enrolled) + mevcut yoklama durumları

PUT    /api/v1/trainings/{course_id}/sessions/{session_id}/attendance
       Body: AttendanceBulkUpdate
       Response: { updated: int, created: int }
       Kural: UPSERT — varsa güncelle, yoksa oluştur

GET    /api/v1/trainings/{course_id}/attendance/report
       Response: AttendanceReport
       İçerir: kişi bazlı var/yok/mazeret özeti, % devam
```

### Bulk Yoklama Body

```json
{
  "records": [
    {
      "person_id": "uuid",
      "status": "var",
      "check_in_time": "09:00",
      "check_out_time": "11:30",
      "notes": null
    }
  ]
}
```

---

## İş Kuralları (Eski Sistemden Taşınan)

1. **Kapasite kontrolü**: `POST /participants` → aktif enrollment sayısı ≥ `capacity` ise 409 dön
2. **Duplicate enrollment engeli**: aynı `(course_id, person_id)` aktif kayıt varsa 409 dön
3. **Soft cancel**: enrollment sil → `cancelled_at = now()`, `status = 'iptal'`; DB'den silinmez
4. **Attendance UPSERT**: `(session_id, person_id)` zaten varsa UPDATE, yoksa INSERT
5. **Tenant isolation**: tüm sorgu ve yazmalarda `club_id = current_user.club_id` zorunlu; body'den `club_id` kabul edilmez
6. **Eğitmen uyarısı**: `instructor_person_id IS NULL` olan aktif kurslar dashboard uyarılarında gösterilecek (Sprint 6A sonrası)
7. **Audit kaydı**: CREATE / UPDATE / DELETE her işlemde audit_log'a yazılır

---

## Permission Tanımları

```python
# Yeni permission string'leri
"training:read"       # kurs ve oturum listesi
"training:write"      # kurs oluştur/güncelle
"enrollment:write"    # katılımcı kayıt/iptal
"attendance:read"     # yoklama listesi ve rapor
"attendance:write"    # yoklama giriş/güncelleme
```

Rol mapping (eski `RBAC_KAPSAM` karşılığı):

| Rol | İzinler |
|-----|---------|
| `yonetici` | `training:*`, `enrollment:*`, `attendance:*` |
| `sportif_direktor` | `training:*`, `enrollment:*`, `attendance:*` |
| `antrenor` | `training:read`, `enrollment:read`, `attendance:*` |
| `sporcu` | `training:read`, `enrollment:read:own`, `attendance:read:own` |

---

## Pydantic Şema Taslakları

```python
class TrainingCourseBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    class_name: str | None = None
    level: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    schedule_text: str | None = None
    capacity: int = 0
    fee: Decimal = Decimal("0")
    instructor_person_id: UUID | None = None
    status: Literal["planlandi","aktif","tamamlandi","iptal"] = "planlandi"

class TrainingCourseCreate(TrainingCourseBase):
    pass

class TrainingCourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    class_name: str | None = None
    level: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    schedule_text: str | None = None
    capacity: int | None = None
    fee: Decimal | None = None
    instructor_person_id: UUID | None = None
    status: Literal["planlandi","aktif","tamamlandi","iptal"] | None = None
    is_active: bool | None = None

class TrainingCourseOut(TrainingCourseBase):
    id: UUID
    club_id: UUID
    is_active: bool
    enrollment_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AttendanceStatus(str, Enum):
    var = "var"
    yok = "yok"
    izinli = "izinli"   # eski Flask GECERLI set'inden
    gecikti = "gecikti" # eski Flask GECERLI set'inden

class AttendanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID
    status: AttendanceStatus
    check_in_time: time | None = None
    check_out_time: time | None = None
    notes: str | None = None

class AttendanceBulkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[AttendanceRecord]
```

---

## Dosya Yapısı (yeni platform)

```
backend/app/
├── models/
│   └── training.py           # TrainingCourse, TrainingSession,
│                             #   TrainingEnrollment, TrainingAttendance
├── schemas/
│   └── training.py           # Pydantic şemaları (yukarıdaki taslak)
├── api/v1/routers/
│   └── training.py           # tüm endpoint'ler
└── alembic/versions/
    └── 0009_training_core.py # migration
```

---

## Sprint Sınırları — 6A / 6B Kesim Noktası

Sprint 6A **dahil:**
- `training_courses` CRUD
- `training_sessions` CRUD
- `training_enrollments` (kayıt/iptal, kapasite kontrolü)
- `training_attendance` (toplu yoklama + rapor)

Sprint 6A **dışı (6B):**
- Ödeme kaydı takibi (payment_status Sprint 6A'da tutulur, 6B'de payments domain devralır)
- Gelir raporu
- Gecikmiş aidat listesi

---

## Onay Kontrol Listesi (Sprint 6A başlamadan)

- [ ] `0008_training_core` migration şeması onaylandı ← revision="0008", down_revision="0007"
- [ ] API sözleşmesi onaylandı
- [ ] Permission string'leri onaylandı
- [ ] Attendance enum: `var`, `yok`, `izinli`, `gecikti` — kaynak: Flask `GECERLI` set
- [ ] `0009` Academy events/certs için — henüz mevcut değil, sıra gelince oluşturulacak
- [ ] E2E script taslağı: `scripts/sprint6a_e2e.sh`

# MYK Platform V2 — Sistem Analizi

**Tarih:** 2026-08-23  
**Sürüm:** v0.23.1 / `8b96856`  
**Durum:** Lokal ≡ Production (commit farkı yok; yalnızca `docs/sprint18-gap-analysis.md` untracked)

---

## 1. Genel Bakış

| Katman | Teknoloji | Durum |
|---|---|---|
| Backend | FastAPI + SQLAlchemy async (asyncpg) | ✅ Production |
| Frontend | React + Vite + TypeScript + Axios | ✅ Production |
| Veritabanı | PostgreSQL 15 (18 migration, head: 0018) | ✅ Production |
| Cache/Queue | Redis | ✅ Production |
| Object Storage | MinIO (S3-uyumlu) | ✅ Production |
| PDF Servisi | Ayrı container (pdf-service:8001) | ✅ Production |
| CI/CD | GitHub Actions — push/PR + v* tag | ✅ Aktif |
| HTTPS | ❌ HTTP only (46.224.26.120:18081) | ⚠️ DNS bekliyor |
| SMTP | Yapılandırılmış ama pasif | ⚠️ İsteğe bağlı |

---

## 2. Sunucu vs Lokal Fark

```
Lokal HEAD  : 8b96856  (v0.23.1)
Production  : 8b96856  (v0.23.1)
Fark        : YOK — birebir aynı commit
```

Untracked (commit edilmemiş, yalnızca lokal):
- `docs/sprint18-gap-analysis.md`
- `docs/system-analysis-v0.23.1.md` (bu dosya)

Production sunucusunda farklı olan (repo dışı, kasıtlı):
- `/opt/myk/production/myk-platform-v2/.env` → `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60` (geçici, HTTPS sonrası 15'e döner)
- `/etc/myk/production.env` → aynı geçici değer

---

## 3. Backend — Tam Router ve Endpoint Envanteri

### 3.1 Aktif Router'lar (main.py'de kayıtlı)

| # | Router | Prefix | Açıklama |
|---|---|---|---|
| 1 | health | `/api/v1/health` | GET — sağlık kontrolü |
| 2 | auth | `/api/v1/auth` | login, logout, refresh, setup, change-password |
| 3 | persons | `/api/v1/persons` | CRUD + guardians alt-resource |
| 4 | avatar | `/api/v1/...` | avatar yükleme/silme/görüntüleme |
| 5 | memberships | `/api/v1/memberships` | başvuru CRUD + PDF + imza |
| 6 | dashboard | `/api/v1/dashboard` | stats |
| 7 | public | `/api/v1/public` | public başvuru + sporcu ön kayıt |
| 8 | academy | `/api/v1/academy` | program, ders, quiz, ilerleme |
| 9 | training | `/api/v1/trainings` | kurs CRUD + katılımcı + seans + yoklama + self-checkin |
| 10 | payments | `/api/v1/payments` | ödeme CRUD + gecikme + rapor |
| 11 | equipment | `/api/v1/equipment` | ekipman CRUD + bakım kayıtları |
| 12 | athletes | `/api/v1/athletes` | sporcu profili + uyarılar |
| 13 | settings | `/api/v1/settings` | kulüp bilgisi + spor dalları |
| 14 | notifications | `/api/v1/notifications` | bildirim listesi + okundu + dispatch |
| 15 | calendar | `/api/v1/calendar` | takvim olayları |
| 16 | documents | `/api/v1/documents` | DMS — belge + revizyon + dosya |

**Eksik (Sprint 18):** `users` router → kullanıcı hesabı yönetimi

### 3.2 Endpoint Detayı

**`/auth`**
```
POST /login          → JWT access + refresh cookie
POST /refresh        → token yenileme (⚠️ HTTP'de Secure cookie çalışmıyor)
POST /change-password
POST /logout
POST /setup          → ilk kulüp + admin kurulumu (production'da kilitli)
GET  /me             → main.py inline (TokenPayload + must_change_password)
```

**`/persons`**
```
GET    /             → sayfalı liste (filtre: rol, aktif)
POST   /             → yeni kişi
GET    /{id}
PATCH  /{id}
DELETE /{id}         → soft delete
GET    /{id}/guardians
POST   /{id}/guardians
PATCH  /{id}/guardians/{gid}
DELETE /{id}/guardians/{gid}
GET    /{id}/athletes
```

**`/memberships`**
```
POST   /                     → başvuru oluştur
GET    /                     → liste
GET    /{id}
PATCH  /{id}
PATCH  /{id}/status          → durum geçişi (submitted→approved→rejected)
DELETE /{id}
POST   /{id}/generate-pdf
GET    /{id}/pdf-url
POST   /{id}/signature
DELETE /{id}/signature
GET    /{id}/signature-url
```

**`/trainings`**
```
GET    /me/self-checkin-sessions          → sporcu: katılabileceği seanslar
GET    /                                  → kurs listesi
POST   /
GET    /{id}
PATCH  /{id}
DELETE /{id}
GET    /{id}/participants
POST   /{id}/participants                 → kayıt
DELETE /{id}/participants/{person_id}
GET    /{id}/sessions
POST   /{id}/sessions
PATCH  /{id}/sessions/{sid}
GET    /{id}/sessions/{sid}/attendance
PUT    /{id}/sessions/{sid}/attendance    → antrenör toplu yoklama
POST   /{id}/sessions/{sid}/self-checkin → sporcu self check-in (+18)
GET    /{id}/attendance/report
```

**`/documents`**
```
GET    /
GET    /{id}
POST   /
PATCH  /{id}
DELETE /{id}
GET    /{id}/revisions
POST   /{id}/revisions
POST   /{id}/revisions/{rid}/publish
GET    /{id}/revisions/{rid}/download
```

---

## 4. Veri Modeli — Tablolar

| Model Dosyası | Tablolar |
|---|---|
| user.py | `users`, `refresh_tokens`, `password_reset_tokens` |
| person.py | `persons`, `person_roles` |
| person_guardian.py | `person_guardians` |
| club.py | `clubs` |
| membership_application.py | `membership_applications` |
| training.py | `training_courses`, `training_sessions`, `training_enrollments`, `training_attendance`, `training_course_instructors`, `training_session_instructors` |
| payment.py | `payments` |
| equipment.py | `equipment`, `equipment_maintenance_records` |
| athlete_profile.py | `athlete_profiles` |
| documents.py | `doc_categories`, `doc_documents`, `doc_revisions`, `doc_revision_files` |
| academy.py | `academy_programs`, `academy_modules`, `academy_lessons`, `academy_lesson_steps`, `academy_enrollments`, `academy_sessions`, `academy_progress`, `academy_quiz_questions`, `academy_quiz_attempts`, `academy_quiz_answers` |
| events.py | `domain_events` |
| notification_delivery.py | `notification_deliveries` |
| audit.py | `audit_logs` |
| sports_branch.py | `sports_branches` |
| member_counter.py | `member_counters` |
| application_counter.py | `application_counters` |

**Toplam: ~30 tablo**

### Migration Durumu
```
0001 initial_schema
0002 persons
0003 avatar_membership
0004 membership_full
0005 member_lifecycle
0006 person_guardians
0007 academy_core
0008 training_core
0009 payments
0010 equipment_core
0011 athlete_profiles
0012 domain_events
0013 dms_core
0014 domain_events_retry
0015 notification_deliveries
0016 delivery_claiming
0017 multi_instructor
0018 attendance_mode          ← HEAD (production'da uygulandı)
```

---

## 5. RBAC — Rol / Yetki Matrisi

16 rol tanımlı (`core/rbac.py`). `require_permission()` FastAPI Depends ile kullanılıyor.

| Rol | Seviye |
|---|---|
| `super_admin` | Tüm izinler (`*`) |
| `kulup_yonetici` | Kullanıcı, sporcu, eğitim, ödeme, kişi tam yönetim |
| `genel_sekreter` | Kullanıcı, belge, etkinlik yönetimi |
| `baskan`, `yk_uyesi` | Geniş read-only + raporlar |
| `muhasebe` | Ödeme tam + kişi read (hassas alanlar maskelenir) |
| `sportif_direktor` | Sporcu + eğitim tam |
| `basantrenor` | Eğitim + yoklama + deniz log |
| `antrenor` | Yoklama + sporcu read + deniz log |
| `personel` | Ekipman + bakım |
| `saglik_sorumlusu` | Sporcu read + sağlık tam |
| `guvenlik_operasyon` | Deniz log + rezervasyon |
| `veli` | Kendi sporcusunu read |
| `sporcu` | Kendi verilerini read + self check-in |
| `uye` | Rezervasyon + profil (kendi) |
| `misafir` | Takvim + rezervasyon read |

Hassas alan maskeleme: `tc_no`, `kan_grubu`, `alerji`, `ozel_durum`, `acil_tel` → `"***"` (muhasebe, personel, antrenor, basantrenor)

---

## 6. Frontend — Sayfa ve Route Envanteri

### Route'lar (App.tsx)
```
/login                        → Login.tsx
/403                          → Forbidden.tsx
/basvuru                      → ApplicationFormPage.tsx (public)
/change-password              → ChangePasswordPage.tsx
/dashboard                    → Dashboard.tsx
/persons, /persons/:id        → PersonsPage, PersonDetailPage
/admin/applications, /:id     → ApplicationsPage, ApplicationDetailPage
/sporcular, /:id              → AthletesPage, AthleteDetailPage
/veliler, /:id                → GuardiansPage, GuardianDetailPage
/uyeler, /:id                 → MembersPage, MemberDetailPage
/antrenorler, /:id            → CoachesPage, CoachDetailPage
/akademi                      → AkademiPage
/akademi/program/:slug        → ProgramPage
/akademi/ders/:slug           → LessonPage
/egitimler, /:id              → TrainingPage, TrainingDetailPage
/yoklama                      → AttendancePage
/katilim                      → SelfCheckinPage
/tekneler, /:id               → (ekipman/tekne)
/odemeler                     → PaymentsPage
/raporlar                     → ReportsPage
/ayarlar                      → SettingsPage
/bildirimler                  → NotificationsPage
/takvim                       → CalendarPage
/belgeler, /:id               → DocumentsPage, DocumentDetailPage
/                             → → /dashboard (redirect)
*                             → NotFound
```

**Eksik route (Sprint 18):** `/kullaniciler` → kullanıcı hesabı yönetimi

### API İstemci Dosyaları
```
auth.ts       — login, logout, refresh, me, changePassword
persons.ts    — CRUD + guardians + roles
athletes.ts   — liste, detay, güncelleme, uyarılar
training.ts   — kurs, seans, katılım, self-checkin
memberships.ts — başvuru CRUD + PDF + imza
documents.ts  — DMS
payments.ts   — ödeme + rapor
equipment.ts  — ekipman + bakım
academy.ts    — program, ders, quiz
notifications.ts
calendar.ts
dashboard.ts
settings.ts
public.ts     — public başvuru
client.ts     — Axios base + interceptor (v0.23.1 düzeltildi)
```

**Eksik (Sprint 18):** `users.ts`

### Mimari Notlar
- **Zustand** — auth state in-memory (JWT localStorage'a yazılmaz)
- **useHeartbeat** — oturum canlı tutma hook'u
- **useAuth** — login/logout/me yönetimi + `myk:session-expired` event dinleyicisi
- **ProtectedRoute** — `must_change_password=true` → `/change-password`'a zorunlu yönlendirme
- **ChangePasswordPage** — tamamlanmış; ilk giriş akışı çalışıyor

---

## 7. CI/CD Pipeline

```
Tetikleyici:
  push main       → CI (lint + test + build)
  PR → main       → CI
  tag v*          → CI + CD (production environment onayı gerekir)

CI adımları:
  1. Shell script syntax (bash -n)
  2. docker compose config doğrulama (.env.production.example stub ile)
  3. Python bağımlılıkları + ruff lint
  4. pytest (SQLite in-memory, tüm testler)
  5. Node bağımlılıkları + Vite build

CD (yalnızca v* tag + manual approval):
  SSH → server_side_deploy.sh
  (pull, build, migrate, up -d, smoke test)

Güvenlik:
  - Secrets env: üzerinden erişilir (log maskeleme)
  - Tag adı regex doğrulaması (injection önlemi)
  - Concurrent deployment engeli (concurrency: group)
  - myk-deploy kullanıcısı docker grubunda
```

---

## 8. Test Kapsamı

**Toplam: ~325 test** (19 dosya)

| Dosya | Test Sayısı |
|---|---|
| test_documents.py | 33 |
| test_training_endpoints.py | 29 |
| test_auth.py | 26 |
| test_membership_applications.py | 22 |
| test_persons.py | 21 |
| test_academy_endpoints.py | 20 |
| test_document_bulk_import.py | 18 |
| test_notification_deliveries.py | 16 |
| test_avatar.py | 16 |
| test_public_apply.py | 15 |
| test_person_guardians.py | 15 |
| test_rbac.py | 14 |
| test_pg_migrations.py | 11 |
| test_academy_models.py | 11 |
| test_dispatch_retry.py | 10 |
| test_storage.py | 9 |
| test_membership_approval.py | 8 |
| test_migration_0003.py | 7 |
| test_tenant.py | 4 |

**Test ortamı:** SQLite in-memory (CI) + PostgreSQL migration testi (migrate-pg job)  
**Framework:** pytest + pytest-asyncio + httpx (async test client)

**Test edilmeyen alan:** User yönetimi (router yok, Sprint 18 kapsamı)

---

## 9. Konfigürasyon

### Backend config.py — Tüm Ayarlar

| Ayar | Default | Production |
|---|---|---|
| `myk_env` | `development` | `production` |
| `jwt_access_token_expire_minutes` | `15` | `60` (geçici) |
| `jwt_refresh_token_expire_days` | `7` | `7` |
| `jwt_algorithm` | `HS256` | `HS256` |
| `max_upload_mb` | `15` | `15` |
| `storage_backend` | `local` | `s3` (MinIO) |
| `storage_bucket` | `myk-person-media` | production değeri |
| `storage_bucket_documents` | `myk-documents` | production değeri |
| `allowed_origins` | `["http://localhost:5173"]` | production URL |
| `cors_allow_credentials` | `True` | `True` |
| `allow_public_setup` | `True` | `False` (validator engeller) |
| `smtp_*` | boş | yapılandırıldı ama pasif |
| `pdf_service_url` | `http://pdf-service:8001` | iç ağ |
| `log_level` | `INFO` | `WARNING` |

### Cookie Güvenliği
```python
_COOKIE_KWARGS = {
    "httponly": True,
    "samesite": "lax",
    "secure": settings.myk_env == "production"  # production=True → HTTP'de çalışmaz
}
```
**⚠️ Kritik:** HTTP üzerinde `Secure=True` cookie → refresh token browser tarafından kaydedilmiyor → oturum 60 dakika sonra sona eriyor. Kalıcı çözüm: HTTPS.

---

## 10. Bilinen Açık Sorunlar

| # | Sorun | Etki | Çözüm |
|---|---|---|---|
| S1 | HTTP — Secure cookie çalışmıyor | Oturum 60 dk sonra sona eriyor | DNS + HTTPS (Let's Encrypt) |
| S2 | DNS: panel.mersinyelken.org.tr → 195.201.202.132 (yanlış sunucu) | Alan adı ulaşılamıyor | DNS A kaydı → 46.224.26.120 |
| S3 | `User` router yok | Yönetici arayüzden kullanıcı hesabı yönetemiyor | Sprint 18 |
| S4 | SAWarning: Payment.person relationship overlap | Log kirliliği | Düşük öncelik |
| S5 | SAWarning: Equipment.assigned_person overlap | Log kirliliği | Düşük öncelik |
| S6 | SMTP pasif | E-posta daveti gönderilemez | HTTPS sonrası |

---

## 11. Sprint Geçmişi

| Sprint | Versiyon | Kapsam | Durum |
|---|---|---|---|
| 1–12 | v0.1–v0.19 | Temel altyapı, kişi, üyelik, DMS, ödeme, ekipman, akademi | ✅ |
| 13–15 | v0.20–v0.21 | Eğitim modülü, çoklu antrenör | ✅ |
| 16 | v0.22 | Bildirimler, takvim, belgeler | ✅ |
| 17 | v0.23.0 | Attendance mode split (adult_self_checkin + coach_daily), 6/6 UAT | ✅ |
| 17-hotfix | v0.23.1 | JWT env passthrough + interceptor promise leak düzeltmesi | ✅ |
| **18** | **v0.24** | **Kullanıcı hesabı yönetimi** | 🔲 Planlandı |

---

## 12. Sıradaki Adımlar

**Blocker (HTTPS):**
1. DNS: `panel.mersinyelken.org.tr` A kaydı → `46.224.26.120`
2. `certbot --nginx -d panel.mersinyelken.org.tr`
3. JWT expire → 15'e geri al
4. Gerçek kullanıcı kabulü başlar

**Sprint 18 (DNS bağımsız, geliştirme devam eder):**
- Bkz. `docs/sprint18-gap-analysis.md`
- Backend: `schemas/user.py` + `routers/users.py` (CRUD + reset-password)
- Frontend: `pages/users/UsersPage.tsx` + `UserFormModal.tsx`
- Migration: `person_id` UNIQUE kısıt (0019)

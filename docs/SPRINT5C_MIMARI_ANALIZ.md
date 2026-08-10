# Sprint 5C — Mimari Entegrasyon Analizi

**Tarih:** 2026-08-08
**Analiz tabanı:** Gerçek dosya okuması (varsayım yok)
**Sonuç:** Seçenek B — Tam Konsolidasyon

---

## 1. Flask LMS Envanteri

### Genel Yapı

- **Toplam Python dosyası:** 38 (test ve BACKUP dizinleri hariç)
- **Giriş noktası:** `app.py` — 2182 satır, monolitik yapı (factory yok, tek modül)
- **Blueprints:** `academy` (blueprints/academy.py), `documents`, `import_docs`
- **KnotPlayer test:** `tests/test_knotplayer_smoke.py` mevcut

### Veritabanı Tabloları

`app.py` içindeki `SCHEMA` sabitinden doğrudan çıkarılan tablolar:

| Tablo | Açıklama |
|---|---|
| `kulupler` | Tenant (kulüp) kayıtları |
| `kullanicilar` | Kullanıcı hesapları (integer PK) |
| `sporcular` | Sporcu profilleri |
| `veli_sporcu_iliskileri` | Veli-sporcu bağlantısı |
| `kurslar` | Fiziksel kurslar |
| `kayitlar` | Kursa kayıt |
| `odemeler` | Ödemeler |
| `ekipmanlar` | Ekipman envanteri |
| `yoklama` | Devamsızlık takibi |
| `deniz_loglari` | Denize çıkış logları |
| `belgeler` | Doküman yönetimi |
| `uygunsuzluklar` | Uygunsuzluk takibi |
| `ajan_raporlari` | Otomatik ajan raporları |
| `audit_log` | Denetim izi |
| `bildirim_kuyrugu` | Bildirim kuyruğu |
| `rezervasyonlar` | Ekipman rezervasyonu |
| `etkinlikler` | Etkinlik takvimi |

**Migration 0006 ile eklenen Academy tabloları (12 tablo):**

`academy_programs` → `academy_modules` → `academy_lessons` → `academy_lesson_steps`, `academy_enrollments`, `academy_sessions`, `academy_events`, `academy_progress`, `academy_quiz_questions`, `academy_quiz_attempts`, `academy_quiz_answers`, `academy_certificates`

Tüm tablolarda `tenant_id INTEGER NOT NULL` zorunlu. Migration 0007–0009 ayrıca DMS (Doküman Yönetimi), çelişki çözümü tabloları ekliyor.

### Auth Yöntemi

- **JWT** (`PyJWT` kütüphanesi, HS256)
- **Şifre hash:** Argon2 (`argon2-cffi`)
- **Token claims:** `sub` (kullanici_id int), `kulup_id` (int), `rol`, `ver` (token_version), `jti`, `iss`, `aud`
- **Token invalidation:** DB'deki `token_version` alanı increment edilir
- **Cookie desteği:** `Authorization: Bearer` hem `myk_token` cookie destekli
- **Süre:** `MYK_JWT_EXPIRY` (varsayılan 8 saat)

### Tenant Modeli

Var, güçlü: `kulup_id INTEGER` her tabloda zorunlu FK. Tüm sorgular `AND kulup_id=?` ile yalıtılmış. `slug` alanı üzerinden kulüp tespiti. FastAPI'nin `club_id UUID` yapısıyla özdeş mantık, farklı tip.

### RBAC

9 rol: `super_admin, yonetici, muhasebe, sportif_direktor, antrenor, personel, veli, sporcu, uye`. Namespace tabanlı izin matrisi (`belge:*`, `egitim:read` gibi). `own` scope veli ve sporcu için.

### KnotPlayer

- **Motor:** `static/knots/knotplayer.js` — saf JS (framework bağımsız), anime.js adaptörü
- **Timeline formatı:** `static/knots/{slug}/timeline.json`

```json
{
  "$schema": "myk/knotplayer-timeline/v1",
  "slug": "izbarco",
  "version": 1,
  "locale": "tr-TR",
  "duration_ms": 42000,
  "audio": null,
  "viewBox": "0 0 480 290",
  "colors": { ... },
  "steps": [
    {
      "id": 1,
      "title": "Kroz oluştur",
      "audio_range": [0, 6200],
      "paths": [{"id": "...", "d": "M...", "stroke": "rope_main", "animated": true, "layer": 1}],
      "labels": [...]
    }
  ]
}
```

- **Mevcut bağlar:** Yalnızca `izbarco` (`_KNOT_SLUGS = frozenset({'izbarco'})`)
- **Animasyon kütüphanesi:** anime.js v3 (vendor klasöründe offline)

### Quiz Motoru

- **Soru tipi:** Tek doğru cevaplı çoktan seçmeli (A/B/C/D harfleri)
- **Cevap saklama:** `dogru_harf` DB'de saklanır, frontend'e **hiçbir zaman gönderilmez**
- **Seçenekler:** `secenekler_json` TEXT kolonu (JSON array)
- **Doğrulama:** Sunucu tarafı — `secilen_harf.upper() == dogru_harf`
- **Geçiş eşiği:** `dogru / toplam >= 0.6` (yüzde 60)
- **Quiz bitişinde:** Açıklamalar ve doğru cevaplar iade edilir (sadece sonuç ekranında)
- **Ders tamamlanması:** Yalnızca quiz geçişi sonrası backend tarafından `tamamlandi` yazılır — istemci bunu set edemez

### Progress / Heartbeat Mekanizması

- **Endpoint:** `POST /api/academy/heartbeat` — frontend her 15 saniyede çağırır
- **Koşul:** Yalnızca sekme görünür + pencere odaklanmış + son 60s aktivite varsa
- **Sunucu zamanı yetkili:** İstemci zamanı kabul edilmez
- **Delta hesabı:** `min(gerçek_delta_saniye, 20)` — maksimum 20 saniye kabul, sapma toleransı
- **Çift tablo:** `academy_sessions` (anlık oturum) + `academy_progress` (kümülatif süre)
- **IP saklama:** HMAC-SHA256 hash (`ip_hash`) — plaintext IP kaydedilmez (KVKK)
- **Ders tamamlanma yüzdesi:** Animasyon adımından `min(80, adim/toplam*80)`, kalan 20% quiz'den. Yüzde hiçbir zaman düşürülmez (MAX logic).

### Frontend / Template Yapısı

- **Jinja2 server-rendered templates** — SPA değil
- `templates/academy/` → panel.html, d1_baglar.html, d1_guvenlik.html, d1_isaretler.html, d1_ruzgar.html, base_lesson.html
- `templates/knots/` → izbarco.html (public), izbarco_akademi.html (kayıt gerekli)
- Static: Bootstrap 5, anime.js, knotplayer.js — hepsi vendor/ altında offline
- **İki route:** `/gemici-baglari/{slug}` (halka açık), `/akademi/gemici-baglari/{slug}` (D1 kayıtlı)

### Veritabanı

- **SQLite** (`myk_v2.db`) + WAL mode
- **Alembic** migrations: 0001–0009 (9 migration)
- **Beklenen migration:** `EXPECTED_MIGRATION = '0009'`

### Kritik Bağımlılıklar

```
flask, flask-cors, argon2-cffi, PyJWT, gunicorn,
marshmallow, python-magic, redis, alembic, pymupdf,
python-docx, bleach
```

---

## 2. FastAPI Platform — Mevcut Durum

### Mevcut Tablolar

| Migration | Tablolar |
|---|---|
| 0001 | clubs, users, refresh_tokens, audit_logs |
| 0002 | persons, person_roles, sports_branches |
| 0003 | persons.avatar_object_key, membership_applications, application_counters |
| 0004 | membership_applications (full schema) |
| 0005 | persons.member_number, persons.must_change_password, member_counters, password_reset_tokens, users.person_id |
| 0006 | person_guardians |

### Auth Yapısı

- **JWT** + Argon2 (tıpkı Flask LMS gibi)
- **Access + Refresh token** (Flask LMS'te yalnızca access token)
- `club_id` **UUID** — tenant isolation. Her tabloda FK.
- Async Redis rate limiting
- Pydantic v2 (`extra=forbid`) şema doğrulama
- PostgreSQL + asyncpg

### Mevcut Route'lar

`/api/v1/auth/*`, `/api/v1/persons/*`, `/api/v1/memberships/*`, `/api/v1/dashboard`, `/api/v1/health`, `/api/v1/avatar/*`, `/api/v1/public/*`

### Kritik Eksikler

Academy, KnotPlayer, Quiz, Progress, Heartbeat, Certificate için sıfır tablo ve sıfır endpoint mevcut.

---

## 3. Üç Seçenek Karşılaştırması

*Puan: 1=kötü/zor, 5=iyi/kolay*

| Kriter | A: Ayrı Servis + SSO | B: Tam Konsolidasyon | C: Flask İç Servis |
|---|---|---|---|
| Teknik borç | 1 | 5 | 3 |
| SSO karmaşıklığı | 1 | 5 | 3 |
| DB tutarlılığı | 1 | 5 | 2 |
| Tenant isolation | 2 | 5 | 3 |
| Deployment karmaşıklığı | 1 | 5 | 2 |
| Test edilebilirlik | 2 | 5 | 3 |
| Bakım maliyeti (2 yıl) | 1 | 5 | 3 |
| SaaS ölçeklenebilirliği | 1 | 5 | 2 |
| **Toplam** | **10/40** | **40/40** | **21/40** |

**Seçenek A sorunları:** İki JWT secret, iki DB (SQLite vs PostgreSQL), SSO köprüsü için custom token exchange, integer vs UUID tenant ID uyumsuzluğu, SQLite SaaS için ölçeklenmez.

**Seçenek C sorunları:** İki DB arasında FK tutarlılığı olmaz, kullanıcı ID çakışmaları olur, iç HTTP çağrıları latency ve debug maliyeti getirir.

---

## 4. Öneri: Seçenek B — Tam Konsolidasyon

Academy/KnotPlayer/Quiz FastAPI'ye taşınır. Flask LMS akademi kodu kaldırılır.

### 5 Bağımsız Gerekçe

1. **Tenant modeli özdeş:** Flask `kulup_id INTEGER` → FastAPI `club_id UUID`. Yapı aynı, sadece tip farklı. Migration'da tek değişen FK tipi.

2. **KnotPlayer sıfır migration gerektiriyor:** `knotplayer.js` ve `anime-adapter.js` saf JS, framework bağımsız. `timeline.json` MinIO'ya yüklenip URL ile serve edilir. Bu dosyalara tek satır dokunulmaz.

3. **Academy şema tasarımı zaten sağlam:** `0006_academy_tables.py`'daki 12 tablo UUID PK ile yeniden yazılmak için 2-3 saat iş. Mantık özdeş.

4. **Quiz engine küçük:** 150 satır Python (3 endpoint). FastAPI async router'a doğrudan uyarlanır. En kritik güvenlik kuralı (cevap frontend'e gitmiyor) zaten enforced.

5. **Flask LMS deploy edilmedi.** Hiç production'a çıkmamış. Ayrı servis olarak çıkarmak yerine temiz PostgreSQL üzerinde FastAPI içinde çıkarmak net olarak daha az iştir.

### Ne Reuse Edilir, Ne Yeniden Yazılır

**Doğrudan reuse (kod değişmez):**
- `static/knots/knotplayer.js` + `static/knots/adapters/anime-adapter.js`
- `static/knots/*/timeline.json` (tüm bağ animasyonları)
- Quiz mantığı Python kodu (~4 saat uyarlama, yeniden yazma değil)
- Heartbeat delta hesabı ve session mantığı (~3 saat)
- `seed_academy.py` verileri (D1/D2/D3, sorular) — PostgreSQL için uyarlanır

**Yeniden yazılır:**
- Jinja2 templates → React components (frontend sprint)
- SQLite sorgular → SQLAlchemy async ORM
- Integer `kulup_id` → UUID `club_id` FK referansları
- Blueprint route'lar → FastAPI APIRouter (`/api/v1/academy/...`)

---

## 5. Önerilen Hedef Mimari

### Mimari Kararlar (Kod Öncesi Kapanmış Sorular)

**Karar 1 — person_id vs user_id ayrımı:**

`User` kimlik doğrulama hesabıdır (email + parola + JWT). `Person` ise sporcu/üye/veli gibi domain kimliğidir. Eğitim geçmişi, sertifika ve ilerleme kişiye aittir, hesaba değil. Kurallar:

- `academy_enrollments`, `academy_progress`, `academy_certificates` → `person_id UUID FK persons` kullanır
- `academy_sessions`, `academy_events` → `user_id UUID FK users` kullanır (audit/IP tracking için auth hesabı gerekli)
- JWT'den `current_user.person_id` ile `person_id` elde edilir; `Person` olmayan kullanıcılar (admin API key vb.) için enrollment yapılamaz

**Karar 2 — lesson slug uniqueness (multi-tenant):**

MVP'de İzbarço gibi içerikler tüm kulüpler için globaldir (Mersin Yelken Kulübü'ne özel bir bağ yok). Bu durum iki seçenek sunar:

- **Seçenek i — Global catalog + club config:** `academy_lessons.slug UNIQUE` (global) + `academy_lesson_configs(club_id, lesson_id)` tablosu kulübün o dersi aktif ettiğini gösterir. Kulübe özel içerik yoksa en temiz yol.
- **Seçenek ii — Tenant-scoped:** `UNIQUE (club_id, slug)`, her kulüp kendi içerik kopyasına sahip olur.

**MVP için karar: Seçenek i — Global catalog.** İzbarço tek slug. Kulüpler enrollment/config üzerinden ayrışır. Gelecekte kulübe özel içerik gerekirse `club_id` nullable yapılır veya `lesson_configs` tablosu genişletilir.

**Karar 3 — Migration kapsamı:**

MVP için gerçekten kullanılan 10 tablo `0007`'de açılır. `academy_events` ve `academy_certificates` `0008`'e ertelenir (İzbarço MVP'sinde kullanılmıyor, gereksiz production riski).

`0007`'deki tablolar: `academy_programs`, `academy_modules`, `academy_lessons`, `academy_lesson_steps`, `academy_enrollments`, `academy_sessions`, `academy_progress`, `academy_quiz_questions`, `academy_quiz_attempts`, `academy_quiz_answers`

`0008`'deki tablolar: `academy_events`, `academy_certificates`

### Yeni Tablolar (migration 0007 — MVP kapsamı)

```sql
-- Global content catalog (club_id nullable = global; NOT NULL = kulübe özel)
academy_programs        (id UUID PK, club_id UUID NULLABLE FK clubs, kod TEXT, ad TEXT, seviye INT,
                          is_global BOOL DEFAULT true, ...)
academy_modules         (id UUID PK, program_id UUID FK, sira INT, ad TEXT, ...)
academy_lessons         (id UUID PK, module_id UUID FK, sira INT, slug TEXT UNIQUE,  -- global slug
                          ad TEXT, ders_tipi TEXT, ...)
academy_lesson_steps    (id UUID PK, lesson_id UUID FK, sira INT, tip TEXT, data_json JSONB)

-- Club-scoped (her kulüp kendi kayıt/ilerleme verisine sahip)
academy_enrollments     (id UUID PK, club_id UUID NOT NULL FK clubs,
                          person_id UUID NOT NULL FK persons,    -- domain kimliği
                          program_id UUID FK, status TEXT, enrolled_at TIMESTAMPTZ, ...)

academy_sessions        (id UUID PK, club_id UUID NOT NULL FK clubs,
                          user_id UUID NOT NULL FK users,        -- auth hesabı (audit)
                          person_id UUID NOT NULL FK persons,    -- kimin seansı
                          lesson_id UUID FK, ip_hash TEXT, started_at TIMESTAMPTZ, ...)

academy_progress        (id UUID PK, club_id UUID NOT NULL FK clubs,
                          person_id UUID NOT NULL FK persons,    -- domain kimliği
                          lesson_id UUID FK,
                          tamamlandi BOOL DEFAULT false,
                          yuzde INT DEFAULT 0,                   -- MAX logic, hiç düşmez
                          toplam_sure_sn INT DEFAULT 0,
                          UNIQUE (club_id, person_id, lesson_id))

-- Quiz (questions global, attempts club-scoped)
academy_quiz_questions  (id UUID PK, lesson_id UUID FK, sira INT,
                          soru_metni TEXT, options JSONB, correct_letter TEXT)  -- correct_letter backend-only

academy_quiz_attempts   (id UUID PK, club_id UUID NOT NULL FK clubs,
                          person_id UUID NOT NULL FK persons,    -- domain kimliği
                          lesson_id UUID FK,
                          basladi_at TIMESTAMPTZ, bitti_at TIMESTAMPTZ,
                          dogru INT, toplam INT, gecti BOOL, ...)

academy_quiz_answers    (id UUID PK, club_id UUID NOT NULL FK clubs,
                          attempt_id UUID FK, question_id UUID FK,
                          secilen_harf TEXT, dogru_mu BOOL)
```

### Migration 0008 (MVP sonrası)

```sql
academy_events          (id UUID PK, club_id UUID NOT NULL FK clubs,
                          user_id UUID NOT NULL FK users,
                          session_id UUID FK, event_type TEXT, payload JSONB, ...)

academy_certificates    (id UUID PK, club_id UUID NOT NULL FK clubs,
                          person_id UUID NOT NULL FK persons,    -- domain kimliği
                          program_id UUID FK, cert_no TEXT UNIQUE,
                          verildigi_tarih DATE, ...)
```

### API Route Yapısı

```
GET  /api/v1/academy/programs                    — kulübün programları
GET  /api/v1/academy/programs/{slug}             — program detayı
POST /api/v1/academy/enrollments                 — programa kayıt (admin)

GET  /api/v1/academy/lessons/{slug}              — ders + ilerleme durumu
POST /api/v1/academy/heartbeat                   — 15s heartbeat
POST /api/v1/academy/session/close               — oturumu kapat

GET  /api/v1/academy/progress/{lesson_id}        — ders ilerlemesi
POST /api/v1/academy/knot/progress               — KnotPlayer adım ilerlemesi
GET  /api/v1/academy/knot/{slug}/timeline        — timeline.json serve

GET  /api/v1/academy/quiz/{lesson_id}/questions  — sorular (cevapsız)
POST /api/v1/academy/quiz/{lesson_id}/start      — girişim başlat
POST /api/v1/academy/quiz/answer                 — cevap gönder
POST /api/v1/academy/quiz/{attempt_id}/finish    — quiz bitir + skor

GET  /api/v1/academy/certificates               — kişinin sertifikaları

# Admin
GET  /api/v1/academy/admin/progress-report
POST /api/v1/academy/admin/quiz-questions
POST /api/v1/academy/admin/enrollments
```

### Tenant Isolation

```python
# Global content: club_id filtresi YOK (slug global)
async def get_academy_lesson(lesson_slug: str, user=Depends(get_current_user), db=Depends(get_db)):
    lesson = await db.execute(
        select(AcademyLesson).where(AcademyLesson.slug == lesson_slug)
    )
    # Enrollment kontrolü: kullanıcının kulübü bu derse kayıtlı mı?
    enrollment = await db.execute(
        select(AcademyEnrollment)
        .where(AcademyEnrollment.club_id == user.club_id)
        .where(AcademyEnrollment.person_id == user.person_id)
        .where(AcademyEnrollment.program_id == lesson.module.program_id)
    )

# Club-scoped veriler: her zaman club_id + person_id filtresi
async def get_lesson_progress(lesson_id, user=Depends(get_current_user), db=Depends(get_db)):
    return await db.execute(
        select(AcademyProgress)
        .where(AcademyProgress.club_id == user.club_id)   # tenant
        .where(AcademyProgress.person_id == user.person_id)  # kişi
        .where(AcademyProgress.lesson_id == lesson_id)
    )
```

### KnotPlayer Assets — MinIO Layout

```
myk-assets/
└── knots/                         ← global (tenant-agnostic)
    ├── knotplayer.js
    ├── adapters/
    │   └── anime-adapter.js
    └── izbarco/
        ├── timeline.json
        └── poster.svg

clubs/{club_id}/knots/{slug}/      ← kulübe özel asset'ler (gelecek)
```

Backend, `timeline.json`'ı MinIO'dan okur veya nginx static serve eder. KnotPlayer URL parametresiyle çalışır:

```js
const kp = KnotPlayer.init('kp', {
  adapter: 'anime',
  timelineUrl: '/api/v1/academy/knot/izbarco/timeline'
})
```

### MVP: "İzbarço" Dersi için Minimum Scope

**Hedef:** Deniz Akademisi → Gemici Bağları → İzbarço — tek ders production'da çalışır.

**Migration 0007:** 10 tablo UUID PK ile (`events` ve `certificates` ertelendi — MVP'de kullanılmıyor)

**Seed:** `scripts/seed_academy.py` — D1 programı + İzbarço dersi + quiz soruları (PostgreSQL)

**Backend — 8 endpoint:**
1. `GET /api/v1/academy/programs/d1` — D1 programı
2. `POST /api/v1/academy/enrollments` — admin panelden kayıt
3. `GET /api/v1/academy/lessons/izbarco` — ders + kullanıcı ilerlemesi
4. `POST /api/v1/academy/heartbeat` — 15s heartbeat
5. `POST /api/v1/academy/knot/progress` — animasyon adım ilerlemesi
6. `GET /api/v1/academy/quiz/{lesson_id}/questions` — sorular
7. `POST /api/v1/academy/quiz/{lesson_id}/start` — girişim başlat
8. `POST /api/v1/academy/quiz/{attempt_id}/finish` — bitir + tamamlanma yaz

**Static assets (değişmez):**
- `knotplayer.js` + `anime-adapter.js` → MinIO/nginx static
- `izbarco/timeline.json` → MinIO/nginx static

**Frontend:** React sayfası — KnotPlayer embed + heartbeat hook + quiz UI

**Süre tahmini:**
- Backend (migration + 8 endpoint + testler): 4-6 gün
- Frontend (React KnotPlayer wrapper + quiz UI): 3-5 gün

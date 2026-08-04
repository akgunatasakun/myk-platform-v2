# MYK Platform V2 — MVP Kapsamı
**Faz 1 Çıktısı · 2026-07-30**

---

## 1. MVP Tanımı

MVP (Minimum Viable Product), mevcut MYK_Yazilim'deki tüm fonksiyonel modülleri **yeni teknoloji yığınında çalışır hale getiren** ve **production güvenlik standartlarını karşılayan** ilk sürümdür.

**MVP = Mevcut işlevsellik + Yeni altyapı**
- FastAPI + React + PostgreSQL + Docker
- Tüm güvenlik gereksinimleri (Argon2, JWT refresh, TC şifreleme)
- Tüm mevcut modüller çalışır (hiçbir iş mantığı kaybolmaz)

---

## 2. MVP Dışı Tutulanlar (Phase 2'ye)

- Yarış / Regatta modülü
- MFA (TOTP)
- Celery arka plan görevleri
- Push notification
- S3 nesne depolama (MVP'de yerel dosya sistemi kalabilir)
- Analytics / raporlama dashboard
- TYF/ISAF harici entegrasyon
- Çoklu kulüp yönetim paneli (super_admin UI)

---

## 3. MVP Modülleri

### Backend (FastAPI)

| Modül | Endpoint Ailesi | Sprint Tahmini |
|---|---|---|
| Auth & Oturum | `/api/v1/auth/*` | 1 |
| Kulüp Kurulum | `/api/v1/setup` | 1 |
| Kullanıcı & Rol | `/api/v1/users/*` | 1 |
| Sporcu | `/api/v1/athletes/*` | 2 |
| Kurs & Kayıt | `/api/v1/courses/*`, `/api/v1/enrollments/*` | 2 |
| Yoklama | `/api/v1/attendance/*` | 2 |
| Ödeme | `/api/v1/payments/*` | 3 |
| Ekipman | `/api/v1/equipment/*` | 3 |
| Deniz Logu | `/api/v1/sea-logs/*` | 3 |
| Rezervasyon | `/api/v1/reservations/*` | 3 |
| DMS | `/api/v1/documents/*` | 4 |
| Akademi & KnotPlayer | `/api/v1/academy/*` | 4 |
| Uygunsuzluk | `/api/v1/nonconformities/*` | 4 |
| AI Ajan | `/api/v1/agent/*` | 5 |
| Audit Log | `/api/v1/audit/*` | Sürekli |
| Health | `/api/v1/health` | 1 |

### Frontend (React + TypeScript)

| Ekran Grubu | Bileşenler | Sprint Tahmini |
|---|---|---|
| Auth | Login, logout, token yenile | 1 |
| Dashboard | Özet kart, bildirimler | 2 |
| Üye & Sporcu | Listele, profil, sağlık formu | 2–3 |
| Eğitim | Kurs listesi, kayıt, yoklama | 3 |
| Ödeme | Fatura, gecikme | 3 |
| Ekipman | Envanter, bakım | 4 |
| DMS | Yükle, listele, revizyon | 4 |
| KnotPlayer | Animasyon oynatıcı (taşınan bileşen) | 4 |
| Ajan | Rapor çalıştır, görüntüle | 5 |
| Ayarlar | Kulüp ayarları, kullanıcılar | 5 |

### Altyapı

| Bileşen | Gereksinim |
|---|---|
| Docker Compose | API + Frontend + PostgreSQL + Redis + Nginx |
| Alembic | PostgreSQL migration |
| Nginx | Reverse proxy, HTTPS, CORS |
| Gunicorn / Uvicorn | ASGI server |
| Redis | Rate limiting + session |
| Storage | Yerel dosya sistemi (MVP) |

---

## 4. MVP Güvenlik Gereksinimleri (Tamamı Zorunlu)

| Gereksinim | Detay |
|---|---|
| Parola: Argon2id | time_cost≥2, mem≥64MB |
| JWT: access + refresh çifti | Access 15dk, Refresh 7 gün, HttpOnly cookie |
| TC kimlik şifreleme | PostgreSQL pgcrypto AES-256 |
| Rate limiting | Redis, tenant+email+IP bileşik |
| RBAC backend zorunlu | Frontend kontrolü yeterli değil |
| Tenant izolasyonu | Her sorgu club_id filtreli |
| Bot operasyon modülü | Yapılandırılabilir: yetkili personel, belgeler, kontrol listesi yönetici tanımlar |
| Audit log | Tüm değiştirici işlemler |
| Soft-delete | Belgeler + sporcu + kullanıcı |
| HTTPS zorunlu | Production'da plain HTTP yok |
| .env asla paketle | Şablon env.example, gerçek .env izolasyon dışı |

---

## 5. MVP Kabul Kriterleri

Bir modül MVP'ye hazır sayılmak için şunları karşılamalıdır:

- [ ] Tüm endpoint'ler FastAPI router'da tanımlı ve Pydantic şema doğrulamalı
- [ ] RBAC: Her endpoint `_has_perm()` ile korunmuş
- [ ] Tenant: Her DB sorgusu `club_id` filtreli
- [ ] Test: Minimum unit + integration test; başarılı login, yetkisiz erişim reddi, cross-tenant erişim engellenmiş
- [ ] Audit: Tüm POST/PUT/DELETE → audit_log kaydı
- [ ] Güvenlik: Hassas alanlar maskeleniyor (muhasebe/personel/antrenör)

---

## 6. MVP Başarı Ölçütleri

| Ölçüt | Hedef |
|---|---|
| Test coverage | ≥ %80 |
| Security test geçme | RBAC + tenant isolation + brute-force koruması |
| API yanıt süresi (p95) | ≤ 200ms |
| Deploy yöntemi | Docker Compose, tek komutla ayağa kalkma |
| Migration başarısı | Tüm Sprint 1-9 verileri PostgreSQL'e taşınabilir |

---

*MVP kapsamı, mevcut MYK_Yazilim modülleri ve V2 gereksinim spesifikasyonu temel alınarak belirlenmiştir.*

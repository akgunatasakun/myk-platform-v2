# MYK Platform Birleştirme — Gap Analysis
**Tarih:** 2026-08-10  
**Kaynak:** Eski Flask (`/opt/myk/app.py`) route envanteri vs. yeni FastAPI v0.7.0

---

## Mevcut Durum

| Sistem | URL | Stack |
|--------|-----|-------|
| Eski panel | `panel.mersinyelken.org.tr` → `localhost:8000` | Flask + gunicorn + SQLite |
| Yeni platform | `panel.mersinyelken.org.tr` → `localhost:18081` | FastAPI + React + PostgreSQL |

> Nginx artık yeni platforma yönlendirilmiş. Gunicorn yalnızca referans olarak `localhost:8000`'de yaşıyor.

---

## Modül Bazlı Gap Tablosu

### ✅ TAM — Yeni platformda mevcut, eski referans gerekmiyor

| Modül | Eski Flask | Yeni FastAPI | Not |
|-------|-----------|--------------|-----|
| Auth (giriş/çıkış/token) | `/api/auth/giris`, `/ben`, `/cikis` | `/api/v1/auth/login`, `/me`, `/logout`, `/refresh` | JWT → yeni sistem üstün |
| Kullanıcı kurulum | `/api/kurulum` | `/api/v1/auth/setup` | ✓ |
| Kişi kaydı | `/api/sporcular` CRUD | `/api/v1/persons` CRUD | Person model → veli/sporcu/antrenör hepsi burada |
| Veli–sporcu | `/api/veli-sporcu` | `/api/v1/persons/{id}/guardians` | Sprint 5B ile tamamlandı |
| Üyelik başvurusu | Eski'de yoktu | `/api/v1/memberships` CRUD + PDF + imza | Yeni özellik |
| Şifre değiştir | — | `/api/v1/auth/change-password` | Yeni özellik |
| Avatar | — | `/api/v1/avatar` | Yeni özellik |
| Dashboard stats | `/api/raporlar/dashboard` (kısmi) | `/api/v1/dashboard/stats` | Genişletilecek |
| Deniz Akademisi | `/api/academy/*` (Flask) | `/api/v1/academy/*` | Sprint 5C ile tam taşındı |
| KnotPlayer / Quiz | `/api/academy/quiz/*`, `/heartbeat` | `/api/v1/academy/quiz/*`, `/heartbeat` | Yeni platform üstün |

---

### 🔴 EKSİK — Yeni platformda hiç yok, taşınmalı

#### Sprint 6A — Eğitim & Yoklama (Öncelik: Yüksek)

Eski Flask route'ları:
```
GET  /api/kurslar
POST /api/kurslar
GET  /api/kurslar/{id}
PUT  /api/kurslar/{id}
GET  /api/kayitlar
POST /api/kayitlar
DEL  /api/kayitlar/{id}
GET  /api/yoklama
POST /api/yoklama
GET  /api/yoklama/rapor/{kurs_id}
```

**Önemli ayrım:** Bu fiziksel yelken kursları. Academy = online LMS. İkisi farklı domain.

Hedef FastAPI endpoint'leri:
```
/api/v1/trainings           → Kurs listeleme/oluşturma
/api/v1/trainings/{id}      → Kurs detay/güncelle
/api/v1/trainings/{id}/participants  → Katılımcı kayıt
/api/v1/trainings/{id}/sessions      → Ders oturumları
/api/v1/trainings/{id}/attendance    → Yoklama + rapor
```

Yeni tablolar (migration 0009):
```sql
training_courses     (id, club_id, ad, baslangic, bitis, egitmen_person_id, kapasite)
training_enrollments (id, course_id, person_id, kayit_tarihi, durum)
training_sessions    (id, course_id, tarih, sure_dk)
training_attendance  (id, session_id, person_id, katildi, not)
```

---

#### Sprint 6B — Ödemeler & Aidat (Öncelik: Yüksek)

Eski Flask route'ları:
```
GET  /api/odemeler
POST /api/odemeler
PUT  /api/odemeler/{id}
GET  /api/odemeler/gecikmusler
GET  /api/raporlar/gelir
```

Hedef FastAPI endpoint'leri:
```
/api/v1/payments                → Ödeme listesi (filtre: ödendi/gecikmiş)
/api/v1/payments/{id}           → Detay / güncelle
/api/v1/payments/overdue        → Gecikmiş ödemeler
/api/v1/payments/reports/income → Gelir raporu
```

Yeni tablolar (migration 0010):
```sql
payment_plans   (id, club_id, person_id, aciklama, tutar, vade_tarihi, yil, ay)
payment_records (id, plan_id, odeme_tarihi, odenen_tutar, yontem, not)
```

---

#### Sprint 6C — Ekipman & Bakım (Öncelik: Orta)

Eski Flask route'ları:
```
GET  /api/ekipmanlar
POST /api/ekipmanlar
GET  /api/ekipmanlar/{id}
PUT  /api/ekipmanlar/{id}
GET  /api/ekipmanlar/bakim-gerekli
```

Hedef:
```
/api/v1/equipment               → Ekipman listesi
/api/v1/equipment/{id}          → Detay / güncelle
/api/v1/equipment/maintenance   → Bakım bekleyenler
```

Yeni tablolar (migration 0011):
```sql
equipment         (id, club_id, ad, tip, seri_no, satin_alma_tarihi, durum)
equipment_maintenance (id, equipment_id, tarih, aciklama, maliyet, yapan_person_id)
```

---

#### Sprint 6D — Rezervasyon, Etkinlik, Deniz Logu (Öncelik: Orta)

Eski Flask route'ları:
```
GET  /api/rezervasyonlar
POST /api/rezervasyonlar
PUT  /api/rezervasyonlar/{id}/onayla
POST /api/etkinlikler
GET  /api/etkinlikler
GET  /api/deniz-loglari
POST /api/deniz-loglari
```

Yeni tablolar (migration 0012):
```sql
reservations  (id, club_id, person_id, kaynak_tip, baslangic, bitis, durum)
events        (id, club_id, ad, tarih, konum, aciklama)
sea_logs      (id, club_id, tekne_id, kaptan_person_id, cikis, donus, rota, not)
```

---

#### Sprint 6E — Belgeler / DMS (Öncelik: Düşük — Bağımsız Sprint)

Eski Flask'ta üç ayrı blueprint var:
- `blueprints/documents.py` → DMS core (liste, revizyon, ilişki)
- `blueprints/import_docs.py` → Toplu import + rollback lifecycle

Kapsam büyük, MinIO entegrasyonu gerekli. Üyelik PDF altyapısı (`/api/v1/memberships/.../generate-pdf`) hazır; bunu referans alarak genişletilecek.

---

#### Sprint 6F — Uygunsuzluk & Audit UI (Öncelik: Düşük)

Eski Flask:
```
GET /api/uygunsuzluklar
PUT /api/uygunsuzluklar/{id}
GET /api/audit-log
```

Yeni platformda audit altyapısı var ama UI yok. Uygunsuzluk = kulüp operasyon kalite modülü.

---

#### Sprint 6G — Bildirimler & AI Ajan (Öncelik: En Düşük)

```
GET  /api/bildirimler
POST /api/ajan/calistir
GET  /api/ajan/raporlar
PUT  /api/ajan/raporlar/{id}
```

AI Ajan eski sistemde ISO 9001 uygunsuzluk analizi yapıyor. Bu modülü yeni platforma taşımadan önce 6A–6D'nin tamamlanması şart.

---

## Kritik Mimari Ayrım

```
Fiziksel Kulüp Eğitimi          Online Deniz Akademisi
─────────────────────           ──────────────────────
training_courses                academy_programs
training_enrollments            academy_enrollments
training_attendance             academy_progress
training_sessions               academy_sessions
YTE D1/D2 dönemleri             İzbarço, KnotPlayer
Eğitmen, grup, ücret            Quiz, heartbeat, sertifika
/api/v1/trainings               /api/v1/academy
```

**Bu iki domain aynı tabloya birleştirilmemelidir.**

---

## Kişi (Person) Modeli — Merkezi Domain

Yeni platformdaki `persons` tablosu tüm insan tiplerini karşılar:

| Eski Flask | Yeni Person | Nasıl |
|-----------|-------------|-------|
| Sporcu | Person + `role=sporcu` veya sport_branch ilişkisi | `person_roles` |
| Antrenör | Person + `role=antrenor` | `person_roles` |
| Veli | Person + Guardian ilişkisi | `person_guardians` |
| Kullanıcı | User (auth) + `person_id` FK | ayrı tablolar |
| Üye | Person + Membership | `memberships` |

Eski sistemdeki `/api/sporcular` CRUD'u `persons` + filtre ile karşılanabilir.  
Antrenör görünümü için `person_roles` tablosu genişletilecek.

---

## Önerilen Sprint Sırası

```
v0.7.0 (TAMAMLANDI)
  └── Deniz Akademisi MVP

Sprint 6A — Eğitim & Yoklama          migration 0009
Sprint 6B — Ödemeler & Aidat          migration 0010
Sprint 6C — Ekipman & Bakım           migration 0011
Sprint 6D — Rezervasyon/Etkinlik/Log  migration 0012
Sprint 6E — DMS (Belgeler)            migration 0013
Sprint 6F — Uygunsuzluk & Audit UI    (altyapı hazır)
Sprint 6G — Bildirimler & AI Ajan     (en son)

SON: Gunicorn tamamen kapatılır.
```

---

## Gunicorn Kapatma Şartları (Checklist)

Eski Flask kapat → yalnızca şu koşullar sağlandıktan sonra:

- [ ] Sprint 6A: Tüm fiziksel kurs ve yoklama işlemleri yeni platformda
- [ ] Sprint 6B: Tüm ödeme ve aidat işlemleri yeni platformda
- [ ] Sprint 6C: Ekipman yönetimi yeni platformda
- [ ] Sprint 6D: Rezervasyon ve etkinlikler yeni platformda
- [ ] Kullanıcı sıfırlaması: Eski sistemde hiç veri olmadığı teyit edildi ✅
- [ ] `panel.mersinyelken.org.tr` → yeni platform ✅ (YAPILDI)

---

## Şimdi Yapılacak (v0.7.0 sonrası, Sprint 6A öncesi)

1. Eski Flask app.py içindeki SQLAlchemy model tanımlarını oku
2. `training_courses`, `yoklama` vb. kolon yapısını çıkar
3. Yeni migration 0009 tasarımını kilitle
4. Sprint 6A planını onayla → uygula

Komut (sunucuda):
```bash
grep -nE '^class .*\(db\.Model|^    [a-z_]+ = db\.' /opt/myk/app.py | head -200
```

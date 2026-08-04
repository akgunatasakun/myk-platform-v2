# MYK Platform V2 — Geliştirme Yol Haritası
**Faz 1 Çıktısı · 2026-07-30**

---

## Genel Zaman Çizelgesi

```
Ağustos 2026           Eylül 2026            Ekim 2026             Kasım 2026
├─── Aşama 1 ──────────┤─── Aşama 2-3 ───────┤─── Aşama 4-5 ────────┤─── Aşama 6 ──────────►
│ Analiz & Planlama    │ Altyapı + Çekirdek   │ Operasyon Modülleri  │ Güvenlik + Production
│ [ŞİMDİ]              │ MVP temel            │ MVP tamamlanması     │ Deployment
```

---

## AŞAMA 1 — Analiz ve Planlama (Tamamlandı)

**Süre:** ~1 hafta (Temmuz 2026)  
**Çıktılar:**

- [x] Teknik denetim raporu (`01_TEKNIK_DENETIM_RAPORU.md`)
- [x] Doküman envanteri (`02_DOKUMAN_ENVANTERI.md`)
- [x] Tekrar ve çakışma raporu (`03_TEKRAR_CAKISMA_RAPORU.md`)
- [x] Ana süreç listesi (`04_ANA_SUREC_LISTESI.md`)
- [x] Prosedür listesi (`05_PROSEDUR_LISTESI.md`)
- [x] Veri modeli (`06_VERI_MODELI.md`)
- [x] MVP kapsamı (`07_MVP_KAPSAMI.md`)
- [x] Faz 2 kapsamı (`08_FAZ2_KAPSAMI.md`)
- [x] Risk listesi (`09_RISK_LISTESI.md`)
- [x] Yol haritası (`10_GELISTIRME_YOL_HARITASI.md`)

**Aşama 1 Geçiş Kriteri:** Faz 1 dokümanları yönetici tarafından incelendi ve Aşama 2 mimari geliştirmesinin başlaması onaylandı. ✅

---

## AŞAMA 2 — Mimari ve Altyapı

**Süre:** ~2 hafta  
**Hedef:** Her şeyin üstünde çalışacağı temeli kurmak.

### Sprint 2.1 — Docker + PostgreSQL + FastAPI iskelet
- [ ] `myk-platform-v2/` klasör yapısı (backend/, frontend/, infra/, docs/)
- [ ] `docker-compose.yml` — API + PostgreSQL + Redis + Nginx
- [ ] `.env.example` — tüm değişkenler dokümanlı
- [ ] FastAPI app iskelet + health endpoint
- [ ] Alembic kurulumu + migration 0001 (clubs, users tabloları)
- [ ] `pytest` kurulumu + ilk test çalışıyor

### Sprint 2.2 — Auth & RBAC
- [ ] Argon2id parola hashleme
- [ ] JWT access token (15 dk) + refresh token (7 gün)
- [ ] HttpOnly cookie + Authorization header desteği
- [ ] Redis rate limiting (tenant+email+IP)
- [ ] Rol tablosu + permission matrisi
- [ ] `@require_permission()` FastAPI bağımlılığı
- [ ] Tenant izolasyon middleware
- [ ] Audit log middleware

**Aşama 2 Geçiş Kriteri:** `docker compose up` → login → access+refresh token → korumalı endpoint erişimi çalışıyor. RBAC + tenant izolasyon testi yeşil.

---

## AŞAMA 3 — Çekirdek Modüller

**Süre:** ~3 hafta  
**Hedef:** Kulüp, üye, sporcu, veli, belge, kurs, yoklama.

### Sprint 3.1 — Kişi Yönetimi
- [ ] `persons` + `athletes` + `guardian_athlete` tabloları (migration 0002)
- [ ] Kişi CRUD API (FastAPI router)
- [ ] TC kimlik şifreli alan (pgcrypto)
- [ ] Hassas alan maskeleme (muhasebe/personel/antrenör)
- [ ] Veli–sporcu ilişkisi ve erişim kapsamı
- [ ] React: Sporcu listesi, profil formu

### Sprint 3.2 — Belge Yönetimi (Kişi Belgesi)
- [ ] `person_documents` tablosu (migration 0003)
- [ ] Güvenli dosya yükleme (uzantı + MIME + magic bytes)
- [ ] Belge varlığını yetkisiz kullanıcıya 404 ile gizleme
- [ ] Vize/sağlık raporu bitiş tarihi uyarı motoru
- [ ] React: Belge yükleme, liste, süre durumu

### Sprint 3.3 — Kurs, Kayıt, Yoklama
- [ ] `courses`, `enrollments`, `attendance` tabloları (migration 0004)
- [ ] Online başvuru akışı (taslak → onay → kesin kayıt)
- [ ] Kontenjan kontrolü
- [ ] Yoklama kaydı + devam oranı
- [ ] React: Kurs listesi, kayıt formu, yoklama ekranı

**Aşama 3 Geçiş Kriteri:** Yeni sporcu kaydı → kursa kayıt → yoklama → veli kendi çocuğunu görüyor → başka çocuğu göremiyor. Tüm testler yeşil.

---

## AŞAMA 4 — Operasyon Modülleri

**Süre:** ~2 hafta  
**Hedef:** Ödeme, ekipman, bakım, rezervasyon, bildirim altyapısı.

### Sprint 4.1 — Ödeme
- [ ] `payments` tablosu (migration 0005)
- [ ] Tahakkuk türleri, taksit, indirim, burs
- [ ] Soft-delete (iptal/ters kayıt mantığı)
- [ ] Gecikme uyarısı
- [ ] React: Fatura listesi, ödeme kaydı

### Sprint 4.2 — Ekipman & Bakım
- [ ] `equipment`, `maintenance_records` tabloları (migration 0006)
- [ ] Arıza bildirimi → iş emri → tamamlandı akışı
- [ ] Periyodik bakım takvimi
- [ ] React: Envanter listesi, arıza formu

### Sprint 4.3 — Bildirim Altyapısı
- [ ] Sağlayıcı soyutlama katmanı (in-app / e-posta / SMS / WhatsApp arayüzü)
- [ ] MVP'de: in-app + e-posta (SMTP mock)
- [ ] Şablon motoru (kulüp yöneticisi düzenleyebilir)

**Aşama 4 Geçiş Kriteri:** Ödeme kaydı → makbuz → gecikmiş ödeme uyarısı. Ekipman arızası → bakım tamamlandı. Testler yeşil.

---

## AŞAMA 5 — Doküman Yaşam Döngüsü + AI Ajan

**Süre:** ~2 hafta  
**Hedef:** DMS, kural motoru, ajan.

### Sprint 5.1 — DMS
- [ ] `documents`, `document_revisions` tabloları (migration 0007)
- [ ] Doküman kodu tekil kontrolü (aynı anda iki aktif belge yasak)
- [ ] CONFLICT-001 bot talimatı seçimi UI — yönetici aktif belgeyi DMS üzerinden seçer, eski belgeler otomatik arşivlenir (sert blokaj yok)
- [ ] Revizyon zinciri
- [ ] Durum akışı (taslak → inceleme → onay → yürürlük)
- [ ] React: Doküman listesi, yükleme, revizyon

### Sprint 5.2 — AI Ajan (Seviye 1 + 2)
- [ ] Kural motoru: süresi geçmiş vize, eksik KVKK, kontenjan aşımı, vb.
- [ ] Anomali tespiti: olağan dışı devamsızlık, ekipman hasar tekrarı
- [ ] Ajan aksiyon seviyeleri (bilgi / uyarı / öneri / onay bekleyen)
- [ ] Her ajan işlemi audit_log'a
- [ ] React: Ajan dashboard, bekleyen öneriler

**Aşama 5 Geçiş Kriteri:** Süresi geçmiş sağlık raporlu sporcu denize çıkmaya çalışınca sistem engeli gösteriyor. Aynı doküman koduyla iki aktif belge oluşturulamıyor.

---

## AŞAMA 6 — Güvenlik Testi + Production Deployment

**Süre:** ~2 hafta

### Sprint 6.1 — Güvenlik Testi
- [ ] Penetrasyon testi (en az OWASP Top 10 kontrolü)
- [ ] Tenant izolasyon tam test suite
- [ ] Veli–sporcu erişim sınırı testi
- [ ] Dosya yükleme güvenlik testi (path traversal, zararlı dosya)
- [ ] Brute-force koruması testi
- [ ] Şifreli alan okuma/yazma testi

### Sprint 6.2 — Production Deployment
- [ ] Staging ortamı kurulumu
- [ ] PostgreSQL yedekleme betiği + şifreli yedek testi
- [ ] Nginx HTTPS yapılandırması
- [ ] Monitoring (uptime, hata oranı)
- [ ] `README.md`, `INSTALLATION.md`, `DEPLOYMENT.md` son hali
- [ ] Sunucuya kurulum

**Aşama 6 Geçiş Kriteri:** Güvenlik testleri geçti; yedek alınıp geri yüklendi ve veri bütünlüğü doğrulandı; `https://` üzerinden giriş yapılabiliyor.

---

## Kritik Bağımlılıklar

| Bağımlılık | Neden Kritik | Eylem |
|---|---|---|
| CONFLICT-001 bot talimatı seçimi | Bot modülü yapılandırması için yönetici kararı | Aşama 2 sırasında, blokaj değil |
| PostgreSQL sunucu altyapısı | Aşama 2 başlamadan sunucu hazır olmalı | VPS veya cloud DB seçimi |
| Alan adı + SSL sertifikası | HTTPS Aşama 6 için zorunlu | DNS + Let's Encrypt |
| SMTP/bildirim sağlayıcısı | Bildirimler için API anahtarı | Aşama 4'e kadar yeterli |

---

## Sprint Özeti

| Aşama | Sprint | Süre | Ana Çıktı |
|---|---|---|---|
| 1 | Analiz | 1 hafta | 10 planlama dokümanı ✅ |
| 2 | Altyapı + Auth | 2 hafta | Docker + login + RBAC |
| 3 | Çekirdek | 3 hafta | Sporcu + kurs + yoklama |
| 4 | Operasyon | 2 hafta | Ödeme + ekipman + bildirim |
| 5 | DMS + Ajan | 2 hafta | Doküman yönetimi + kural motoru |
| 6 | Güvenlik + Deploy | 2 hafta | Production'da çalışan MVP |
| **Toplam** | | **~12 hafta** | **Çalışan MVP** |

---

## Faz 2 Başlangıç Kriteri

MVP 30 günlük production pilotu tamamlandıktan sonra Faz 2 planlaması yapılır. Faz 2 kapsamı: Yarış/Regatta, MFA, Celery arka plan görevleri, S3 nesne depolama, TYF entegrasyonu, analytics dashboard. Bkz. `08_FAZ2_KAPSAMI.md`.

---

*Bu yol haritası Aşama 1 analiz çıktıları ve V2 gereksinim spesifikasyonu temel alınarak hazırlanmıştır.*

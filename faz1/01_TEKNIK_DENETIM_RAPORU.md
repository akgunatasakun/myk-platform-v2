# MYK Platform — Teknik Denetim Raporu
**Faz 1 Çıktısı · 2026-07-30 · Durum: Taslak**

---

## 1. Yönetici Özeti

MYK_Yazilim klasöründe iki farklı kod katmanı mevcuttur:

**BACKUP_BEFORE_QA** — Orijinal prototip. Gerçekten 2 dosyadan oluşuyor: `index.html` + `calistir.sh`. Yöneticinin tanımladığı "9 dosyalık prototip" bu versiyona atıfta bulunuyor.

**Mevcut MYK_Yazilim/** — Önceki geliştirme oturumlarında üretilen, 676 dosya ve 82 Python dosyası içeren daha kapsamlı bir Flask uygulaması. Argon2id, JWT, Redis, RBAC, DMS, KnotPlayer, 9 Alembic migration ve 400+ test içermektedir.

**V2 kararı:** Her iki versiyon da referans olarak korunur. MYK Platform V2; FastAPI + React + PostgreSQL + Docker mimarisiyle temiz klasörde (`myk-platform-v2/`) sıfırdan inşa edilecektir.

---

## 2. Orijinal Prototip (BACKUP_BEFORE_QA)

| Özellik | Durum |
|---|---|
| Dosya sayısı | ~2 (index.html + calistir.sh) |
| Veritabanı | SQLite |
| Şifre saklama | SHA-256 tuzsuz |
| Sabit yönetici | admin@myk.com / myk2024 |
| Sabit Flask secret | Evet |
| Docker / Nginx / SSL | Yok |
| Rol tabanlı yetki | Yok |
| Test | Yok |
| Gerçek dosya yükleme | Yok |
| Production deploy | Yapılmamış |

---

## 3. Geliştirilmiş Flask Uygulaması (MYK_Yazilim/)

| Metrik | Değer |
|---|---|
| Toplam dosya | 676 |
| Python dosyası | 82 |
| app.py satır | 2.182 |
| Blueprint | 3 (academy, documents, import_docs) |
| Service katmanı | 4 dosya / 1.889 satır |
| Repository | 2 dosya / 982 satır |
| Alembic migration | 9 versiyon |
| Test dosyası | 33 |
| Test satırı | ~8.000 |

### 3.1 Mevcut Güvenlik Temeli

| Koruma | Durum |
|---|---|
| Argon2id parola | ✅ time_cost=2, mem=64MB |
| JWT access token + HttpOnly | ✅ 8 saat |
| Redis brute-force koruması | ✅ tenant+email+IP bileşik |
| Dosya yükleme: magic bytes | ✅ extension + MIME + imza |
| RBAC 9 rol | ✅ permission matrisi |
| Tenant izolasyonu | ✅ kulup_id her sorguda |
| Hassas alan maskeleme | ✅ muhasebe/personel/antrenör |
| Production secret fail-fast | ✅ DEV_ prefix → sys.exit(1) |
| Audit log | ✅ |
| CONFLICT-001 çakışma yönetimi | ✅ V1: sert blokaj (V2'de yapılandırılabilir uyarı olarak yeniden tasarlandı) |

### 3.2 V2'ye Taşınacak Iş Mantığı

Mevcut sistemdeki şu öğeler V2'ye birebir aktarılmalıdır:
- RBAC matrisi (9 rol, permission yapısı)
- Tenant filtreleme deseni
- DMS çakışma kuralları (CONFLICT-001: yapılandırılabilir uyarı modunda, sert blokaj olmaksızın)
- Audit log gereksinimleri
- Güvenlik prensipleri (backend zorunlu, frontend güvenlik mekanizması değil)

---

## 4. V2 Mimarisi Farkları

| Alan | Mevcut Flask | V2 FastAPI |
|---|---|---|
| Veritabanı | SQLite | PostgreSQL 16 |
| ORM | Ham SQL | SQLAlchemy 2 |
| API | Flask route | FastAPI router + Pydantic |
| Frontend | Jinja2 SSR | React + TypeScript + Vite |
| Arka plan görev | Yok | Celery + Redis |
| Deployment | Manuel SSH + systemd | Docker Compose + Nginx |
| Token | Access only (8s) | Access (15dk) + Refresh (7gün) |
| TC kimlik | Plaintext | pgcrypto AES-256 |
| MFA | Yok | Altyapı hazır (Phase 2) |

---

## 5. Deploy Durumu (2026-07-30)

Sunucu (46.224.26.120) şu an statik HTML site çalıştırıyor. Flask uygulaması deploy edilmemiş. V2 kararı nedeniyle Flask deploy artık isteğe bağlıdır — V2 doğrudan production'a kurulacaktır.

---

*Kaynak: `MYK_Yazilim/` klasör analizi, BACKUP_BEFORE_QA içeriği, Sprint 1–2 kayıtları.*

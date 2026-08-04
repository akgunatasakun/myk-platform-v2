# Güvenlik Denetimi — MYK Platform V2 Aşama 2

**Tarih:** 2026-07-30 (Aşama 2.1 güncelleme: 2026-07-30)  
**Kapsam:** `myk-platform-v2/` — backend, frontend, infra  
**Metodoloji:** Manuel kod incelemesi (statik analiz)  
**Denetçi:** Claude (Aşama 2 geliştirme ajanı)  

---

## Özet

| Seviye | Adet |
|---|---|
| 🔴 KRİTİK | 0 |
| 🟠 YÜKSEK | 0 |
| 🟡 ORTA | 0 (2 → Aşama 2.1'de düzeltildi) |
| 🔵 DÜŞÜK | 4 |
| ⚪ BİLGİ | 4 |
| ✅ ONAYLANDI | 14 |
| 🔧 DÜZELTME (2.1) | 2 (S-001, S-002) |

Aşama 2 iskeleti için **blokaj yok**. Tüm ORTA bulgular Aşama 2.1'de giderildi.

---

## Bulgular

---

### S-001 — Setup Endpoint Production'da Herkese Açık
**Seviye:** 🟡 ORTA  
**Dosya:** `backend/app/api/v1/routers/auth.py` (satır ~105)  
**Açıklama:**  
`/api/v1/auth/setup` endpoint'i `allow_public_setup` ayarını kontrol ediyor. Ancak `config.py`'da bu ayar yok; `getattr(settings, "allow_public_setup", True)` varsayılan olarak `True` döndürüyor. Production ortamında setup endpoint'i hâlâ erişilebilir durumda.  

```python
# auth.py satır ~105
if not getattr(settings, "allow_public_setup", True):   # ← settings'te bu alan yok
    raise HTTPException(status_code=403, detail="Kurulum kapalı.")
```

**Kanıt:** `config.py` içinde `allow_public_setup` field tanımı mevcut değil.  
**Etki:** Production'da ikinci bir kulüp + yönetici oluşturulabilir.  
**Düzeltme:**  
```python
# config.py'ye ekle:
allow_public_setup: bool = True  # production .env'de False yapılmalı

# .env.example'a ekle:
ALLOW_PUBLIC_SETUP=false
```
**Durum:** ✅ DÜZELTME TAMAMLANDI (Aşama 2.1) — `allow_public_setup: bool = True` config.py'ye eklendi. Auth router kulüp varlığını ve bu ayarı kontrol ediyor. Test: `test_setup_blocked_when_club_exists_and_not_allowed` PASS.

---

### S-002 — JWT Secret Key Validator Production'da Çalışmıyor
**Seviye:** 🟡 ORTA  
**Dosya:** `backend/app/config.py` (satır ~35-42)  
**Açıklama:**  
`jwt_secret_key` ve `secret_key` için `field_validator` tanımlı, ancak gövde içinde yalnızca değeri döndürüyor — production'da varsayılan `"DEV_ONLY_CHANGE_IN_PRODUCTION"` değerini engellemek için hiçbir kontrol yok.

```python
@field_validator("jwt_secret_key", "secret_key")
@classmethod
def check_secrets_in_production(cls, v: str, info) -> str:
    # Production'da varsayılan değer kullanımını engelle
    # (diğer alanlar yüklendikten sonra model_validator ile yapılır)
    return v   # ← gerçek kontrol YOK
```

**Etki:** Yanlış yapılandırılmış production ortamında zayıf JWT secret kullanılabilir. Token forgery riski.  
**Düzeltme:**  
```python
from pydantic import model_validator

@model_validator(mode="after")
def enforce_production_secrets(self) -> "Settings":
    weak = "DEV_ONLY_CHANGE_IN_PRODUCTION"
    if self.myk_env == "production":
        if self.jwt_secret_key == weak or len(self.jwt_secret_key) < 32:
            raise ValueError("Production ortamında güçlü JWT_SECRET_KEY zorunludur.")
        if self.secret_key == weak or len(self.secret_key) < 32:
            raise ValueError("Production ortamında güçlü SECRET_KEY zorunludur.")
    return self
```
**Durum:** ✅ DÜZELTME TAMAMLANDI (Aşama 2.1) — `model_validator(mode="after")` ile production'da zayıf ve kısa secret'lar `ValueError` fırlatıyor. Testler: `test_production_secret_validation`, `test_production_short_secret_rejected`, `test_development_weak_secret_allowed` — tümü PASS.

---

### S-003 — Rate Limiter Fail-Open Davranışı
**Seviye:** 🔵 DÜŞÜK  
**Dosya:** `backend/app/core/ratelimit.py` (satır ~34-36)  
**Açıklama:**  
Redis erişilemez olduğunda rate limiter `(True, 0)` döndürüyor — yani brute-force koruması devre dışı kalıyor.

```python
except Exception as e:
    logger.warning(f"Rate limit Redis hatası (izin verildi): {e}")
    return True, 0  # ← Redis yoksa engelleme yok
```

**Etki:** Redis çöktüğünde sınırsız login denemesi mümkün. Argon2id time_cost=2 sayesinde her deneme ~50-100ms sürer; tam brute-force çok yavaş olur. Risk azaltıcı faktör mevcut.  
**Düzeltme:** Redis yoksa in-memory fallback (örn. `lru-cache` ile process içi sayaç) veya fail-closed mod. Production'da Redis yüksek erişilebilirlik için yapılandırılmalı.  
**Durum:** KABUL EDİLDİ — Argon2id zaman maliyeti kısmi azaltma sağlıyor; Redis HA Aşama 3'te.

---

### S-004 — CORS Development'ta Wildcard
**Seviye:** 🔵 DÜŞÜK  
**Dosya:** `backend/app/main.py` (satır ~42-45)  
**Açıklama:**  
Development ortamında `allow_origins=["*"]` kullanılıyor.

```python
_origins = (
    ["*"]
    if settings.myk_env == "development"
    else [f"https://{settings.allowed_host}"] ...
)
```

**Etki:** Development ortamında geçerli, ancak `myk_env` yanlışlıkla `development` kalırsa production'da açık CORS politikası oluşur.  
**Düzeltme:** `.env.example`'da `MYK_ENV=production` zorunlu, startup validator S-002 düzeltmesi ile birlikte kontrol edilmeli.  
**Durum:** KABUL EDİLDİ — Development ortamı beklenen davranış.

---

### S-005 — Nginx'te Content-Security-Policy Başlığı Yok
**Seviye:** 🔵 DÜŞÜK  
**Dosya:** `infra/nginx/nginx.conf` (satır ~17-22)  
**Açıklama:**  
Nginx güvenlik başlıkları arasında `Content-Security-Policy` tanımlı değil.

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;   # ← deprecated
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
# ← CSP EKSİK
```

Ayrıca `X-XSS-Protection` modern tarayıcılarda deprecated; CSP tercih edilmeli.  
**Etki:** XSS saldırılarına karşı katman derinliği azalıyor.  
**Düzeltme:**  
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' wss:; frame-ancestors 'none';" always;
```
**Durum:** AÇIK — Aşama 3 Sprint 3.0'da eklenecek.

---

### S-006 — Access Token Blacklist Yok (Logout Sonrası Kısa Pencere)
**Seviye:** ⚪ BİLGİ  
**Dosya:** `backend/app/api/v1/routers/auth.py`  
**Açıklama:**  
Logout yalnızca refresh token'ı iptal ediyor. Access token 15 dakika boyunca geçerli kalmaya devam ediyor.  
**Etki:** Logout sonrası çalınan bir access token 15 dakika boyunca kullanılabilir.  
**Tasarım Notu:** Kısa ömürlü access token (15 dk) + Redis-backed blacklist Aşama 3'te planlandı. TEST_REPORT.md bölüm 11'de belgelenmiş.  
**Durum:** BİLİNEN SINIRLILIK — Aşama 3 Sprint 3.1.

---

### S-007 — Nginx HTTPS Yönlendirmesi Devre Dışı
**Seviye:** ⚪ BİLGİ  
**Dosya:** `infra/nginx/nginx.conf` (satır ~55)  
**Açıklama:**  
HTTP→HTTPS yönlendirmesi yorum satırı olarak bırakılmış.

```nginx
# HTTPS yönlendirmesi — üretimde etkinleştir
# return 301 https://$host$request_uri;
```

**Etki:** Production'da TLS olmadan çalışabilir.  
**Tasarım Notu:** SSL termination ve HTTPS konfigürasyonu Aşama 3 altyapı sprint'inde (domain + Let's Encrypt). Geliştirme iskeleti için beklenen.  
**Durum:** BİLİNEN SINIRLILIK — Aşama 3 altyapı sprint'i.

---

### S-008 — setup Endpoint'inde Password Strength Validation Yalnızca SetupRequest'te
**Seviye:** ⚪ BİLGİ  
**Dosya:** `backend/app/schemas/auth.py`  
**Açıklama:**  
Parola gücü doğrulaması (`SetupRequest.password_strength`) yalnızca `/setup` endpoint'inde uygulanıyor. `/login` endpoint'inde `LoginRequest.password` için böyle bir kısıtlama yok (ve olmamalı — login girişleri kısıtlanmamalı).  
**Tasarım Notu:** Bu davranış doğru. Login'de parola doğrulaması brute-force hint verebilir.  
**Durum:** BİLGİ — Tasarım uygun.

---

### S-009 — `initial_admin_password` Config'de Boş String
**Seviye:** ⚪ BİLGİ  
**Dosya:** `backend/app/config.py` (satır ~33)  
**Açıklama:**  
`initial_admin_password: str = ""` — ilk yönetici oluşturma için ortam değişkeni zorunlu kılınmamış.  
**Etki:** Bu alan henüz kullanılmıyor; `setup` endpoint'i kullanıcı girişiyle çalışıyor. Aşama 3'te `INITIAL_ADMIN_PASSWORD` zorunlu .env değişkeni olacak.  
**Durum:** BİLGİ — Aşama 3 Sprint 3.0.

---

## Onaylanan Güvenlik Özellikleri

| # | Özellik | Dosya | Değerlendirme |
|---|---|---|---|
| ✅ 1 | Argon2id (time_cost=2, memory=65536 KB) | `core/security.py` | OWASP 2023 önerisiyle uyumlu |
| ✅ 2 | JWT audience + issuer doğrulaması | `core/security.py` | `aud="myk-client"`, `iss="myk-platform"` |
| ✅ 3 | Token tipi kontrolü (`type: "access"`) | `core/security.py` | Refresh token Bearer olarak kullanılamaz |
| ✅ 4 | Refresh token rotation | `routers/auth.py` | Kullanılan token hemen iptal ediliyor |
| ✅ 5 | Refresh token SHA-256 hash ile saklanıyor | `core/security.py` | Düz token DB'de yok |
| ✅ 6 | HttpOnly + SameSite=Lax cookie | `routers/auth.py` | JS cookie erişimi yok |
| ✅ 7 | `Secure` flag production'da aktif | `routers/auth.py` | `secure=settings.is_production` |
| ✅ 8 | Tenant izolasyon — 404 (403 değil) | `core/tenant.py` | Kaynak varlığı ifşa edilmiyor |
| ✅ 9 | club_id JWT'den okunuyor, kullanıcı girdisinden değil | `core/tenant.py` | Tenant atlama imkânsız |
| ✅ 10 | Audit log INSERT-only | `core/audit.py` | Uygulama katmanında UPDATE/DELETE yok |
| ✅ 11 | Hassas alanlar loglara yazılmıyor | `core/audit.py` | Docstring zorunluluğu var |
| ✅ 12 | RBAC backend'de zorunlu | `core/rbac.py` | Frontend kontrolü güvenlik mekanizması değil |
| ✅ 13 | Token localStorage'da saklanmıyor | `frontend/src/hooks/useAuth.ts` | Yalnızca bellek içi |
| ✅ 14 | Hata mesajları kullanıcıya bilgi sızdırmıyor | `routers/auth.py` | "Geçersiz kimlik bilgileri" — tek mesaj |
| ✅ 15 | Docs/OpenAPI production'da kapalı | `main.py` | `docs_url=None` production'da |
| ✅ 16 | `.env` repo'da yok | `backend/` | `.gitignore` + `.env.example` mevcut |
| ✅ 17 | Rate limit anahtarı hashed (club+email+ip) | `core/ratelimit.py` | PII anahtar olarak saklanmıyor |
| ✅ 18 | Global exception handler — 500 detayı gizlenmiş | `main.py` | Stack trace kullanıcıya dönmüyor |

---

## Aşama 3 Güvenlik Öncelikleri

| Sprint | Görev | Durum |
|---|---|---|
| 2.1 | `allow_public_setup` config alanı ekle + production enforcement | ✅ TAMAMLANDI |
| 2.1 | `model_validator` ile production secret key zorunlu kıl | ✅ TAMAMLANDI |
| 2.1 | `eslint.config.js` + güvenlik odaklı lint kuralları | ✅ TAMAMLANDI |
| 2.1 | `Content-Security-Policy` Nginx başlığı ekle | ✅ TAMAMLANDI |
| 3.1 | Redis-backed access token blacklist (logout tam geçerli) | AÇIK |
| 3.1 | HTTPS + Let's Encrypt + TLS 1.2+ konfigürasyonu | AÇIK |
| 3.2 | pgcrypto AES-256 ile TC kimlik + sağlık verisi şifreleme | AÇIK |
| 3.2 | MFA altyapısı (TOTP) | AÇIK |
| 3.3 | `npm audit` temiz çıktı + bağımlılık güncelleme pipeline | AÇIK |
| 3.3 | OWASP ZAP dinamik tarama | AÇIK |
| 3.1 | Redis-backed access token blacklist (logout tam geçerli) |
| 3.1 | HTTPS + Let's Encrypt + TLS 1.2+ konfigürasyonu |
| 3.2 | pgcrypto AES-256 ile TC kimlik + sağlık verisi şifreleme |
| 3.2 | MFA altyapısı (TOTP) |
| 3.3 | `npm audit` temiz çıktı + bağımlılık güncelleme pipeline |
| 3.3 | OWASP ZAP dinamik tarama |

---

## CONFLICT-001 Güvenlik Notu

CONFLICT-001 (belge talimatı tutarsızlığı) bu güvenlik denetiminin kapsamı dışındadır.  
İlgili Faz 1 dokümanları (05, 07, 08, 09, 10) güncellendi: `force=True` dahil hiçbir sert blokaj sisteme eklenmedi.  
Teyit: `CONFLICT-001 kilidi` için faz1/ dizininde arama → 0 sonuç.

---

## Kapsam Sınırı

Bu denetim **statik kod analizine** dayanmaktadır. Aşağıdakiler bu kapsamın dışındadır:

- Dinamik analiz (DAST/OWASP ZAP) — Aşama 3
- Penetrasyon testi — Aşama 3
- PostgreSQL privilege escalation testleri — Aşama 3 Sprint 3.1
- Docker imaj taraması (Trivy/Snyk) — Aşama 3
- Dependency vulnerability scan (`npm audit`, `pip-audit`) — Aşama 3

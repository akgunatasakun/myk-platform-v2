# Sprint 18 — Kullanıcı Hesabı Yönetimi: Gap Analizi

**Tarih:** 2026-08-23  
**Temel:** v0.23.1 / 8b96856  
**Durum:** Kararlar kilitlendi — implementasyona hazır

---

## Mevcut Durum

### Çalışan

| Alan | Durum |
|---|---|
| `User` modeli (person_id, role, is_active, soft delete) | ✅ |
| `Person` + `PersonRole` modeli (must_change_password) | ✅ |
| RBAC matrisi — `kullanici:*` permission tanımlı | ✅ |
| Üyelik onayı üzerinden otomatik User oluşturma | ✅ |
| `POST /auth/change-password` endpoint | ✅ |
| Frontend `ChangePasswordPage` + must_change_password guard | ✅ |
| Persons / Members / Athletes / Coaches sayfaları | ✅ |
| Yetişkin self check-in | ✅ |

---

## Kilitlenmiş Tasarım Kararları

### K1 — User.role ↔ PersonRole: Ayrı Kalacak ✅

`User.role` → giriş ve sistem yetkisi (JWT'ye yazılır).  
`PersonRole` → kişinin kulüp içindeki nitelikleri (filtreleme, görüntüleme).

**Kural:** Otomatik senkronizasyon YOK. Ancak uyumluluk doğrulanacak:
- `User.role = "sporcu"` → bağlı Person aktif ve `sporcu` PersonRole'üne sahip olmalı.
- `User.role = "antrenor"` → bağlı Person `antrenor` PersonRole taşımalı.
- Yönetici/kulup_yonetici gibi rollerde `person_id = NULL` olabilir.

Uyumsuzluk: `POST /users` ve `PATCH /users/{id}` 422 döner.

---

### K2 — Partial Unique Index (person_id) ✅

Normal `UNIQUE(person_id)` yerine:

```sql
CREATE UNIQUE INDEX uq_users_person_id_active
ON users (person_id)
WHERE person_id IS NOT NULL AND is_deleted IS FALSE;
```

**Gerekçe:**
- Aynı kişiye iki aktif hesap bağlanamaz.
- Silinmiş hesabın ardından yeni hesap açılabilir (soft-delete uyumlu).

**Migration 0019 öncesi kontrol:**
```sql
-- Production'da duplicate var mı?
SELECT person_id, COUNT(*) FROM users
WHERE person_id IS NOT NULL AND is_deleted IS FALSE
GROUP BY person_id HAVING COUNT(*) > 1;
```

**Backend:** DB `IntegrityError` → `409 Conflict` ("Bu kişiye zaten aktif hesap bağlı.")

---

### K3 — must_change_password: Tek Kaynak User ✅

**Strateji (2 migration):**

*Migration 0019 (bu sprint):*
1. `users.must_change_password BOOLEAN NOT NULL DEFAULT FALSE` eklenir.
2. Bağlı Person'da `must_change_password = TRUE` olan kayıtlar User'a backfill edilir.
3. `login`, `/auth/me`, `change-password`, `membership_approval` → yalnız `User.must_change_password` okur/yazar.
4. `Person.must_change_password` sütunu bırakılır ama artık okunmaz/yazılmaz.

*Migration 0020 (sonraki sprint):*
5. `Person.must_change_password` sütunu kaldırılır.

**Kural:** Varsayılan `FALSE`. Yeni/resetlenen hesaplarda kod açıkça `TRUE` set eder — "varsayılan True" yapılmaz.

---

### Ek Güvenlik Gereksinimleri ✅

**G1 — Refresh token revoke:**  
Rol değiştirme, pasifleştirme, parola reset, soft delete → ilgili kullanıcının tüm aktif refresh token'ları revoke edilir.  
```python
await db.execute(
    update(RefreshToken)
    .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    .values(revoked_at=datetime.now(timezone.utc))
)
```

**G2 — JWT staleness (eski yetki sorunu):**  
`get_current_user`: JWT decode sonrası DB'den User yüklenir; şunlar kontrol edilir:
- `is_active = False` → **401** (session expired — logout)
- `is_deleted = True` → **401**
- `club_id` eşleşmemesi → **401**
- DB `role` ≠ JWT `role` → **401** (yeniden login — rol değişikliği anında etkili)

**KURAL: is_active/is_deleted/rol uyuşmazlığında 401 döner, 403 değil.** 403 yalnızca yetki eksikliği için kullanılır; frontend tüm 403'leri logout sebebi saymamalı.  
`token_version` (ileriki sprint seçeneği olarak not edildi; bu sprint DB role kontrolü yeterli).

**G3 — Son yönetici koruması:**  
`DELETE /users/{id}` ve `PATCH /users/{id}` (pasifleştirme):  
Kulüpte `role = "kulup_yonetici"` ve `is_active = True` ve `is_deleted = False` olan başka kullanıcı yoksa → `409 Conflict` ("Son aktif yönetici silinemez.").

**G4 — Kendi hesabını silme/pasifleştirme:**  
Kullanıcı kendi hesabını pasifleştiremez veya silemez → `403 Forbidden`.  
(Rol değişikliği kendi hesabında da kısıtlanabilir; yönetici başka bir yöneticiye ihtiyaç duyar.)

**G5 — Geçici parola:**  
`POST /users` ve `POST /users/{id}/reset-password` yanıtında yalnızca bir kez döner.  
Audit log'a YAZILMAZ. Yanıt dışında hiçbir yerde saklanmaz.

**G6 — Ortak servis katmanı:**  
`app/services/user_account_service.py` oluşturulur.  
Hem `membership_approval.py` hem de `users` router bu servisi kullanır (kod tekrarı olmaz).  
`restore_user` da bu serviste tanımlanır (soft-delete geri alma).

**G7 — Audit log:**  
`user_created`, `user_role_changed`, `user_deactivated`, `user_deleted`, `user_password_reset`, `user_restored` olayları `audit_logs` tablosuna yazılır.

**G8 — Rol yükseltme kısıtı (`ASSIGNABLE_ROLES_BY_ROLE`):**  
`kullanici:*` iznine sahip herkes her rolü atayamaz:

| Atayan Rol | Atayabileceği Roller |
|---|---|
| `super_admin` | Tümü |
| `kulup_yonetici` | Kulüp rolleri (`super_admin` hariç) |
| `genel_sekreter` | Operasyonel roller (`kulup_yonetici`, `super_admin` hariç) |
| Diğerleri | Hiçbiri |

**G9 — Soft-delete sonrası e-posta politikası:**  
Mevcut `(club_id, email)` unique index **koşulsuz kalır** — silinmiş User e-postasıyla yeni hesap açılamaz.  
Politika: Silinmiş hesap için yeni kayıt yerine **restore** (`POST /users/{id}/restore`) kullanılır.  
Migration 0019'a e-posta index değişikliği dahil edilmez.

---

## Backend Eksikleri

| # | Eksik | Açıklama |
|---|---|---|
| B1 | `user_account_service.py` | Ortak servis katmanı (G6) |
| B2 | `schemas/user.py` | UserCreate, UserUpdate, UserOut, UserListOut |
| B3 | `routers/users.py` | CRUD + reset-password endpoint'leri |
| B4 | Migration 0019 | must_change_password User'a + backfill + person_id partial unique index (e-posta index'i değişmez) |
| B5 | `GET /users` | Yönetici kullanıcı listesi (sayfalı, rol filtreli) |
| B6 | `POST /users` | Kullanıcı oluşturma + Person bağlantısı + geçici parola |
| B7 | `GET /users/{id}` | Kullanıcı detayı |
| B8 | `PATCH /users/{id}` | Rol değiştirme, aktif/pasif; refresh token revoke |
| B9 | `DELETE /users/{id}` | Soft delete; refresh token revoke |
| B10 | `POST /users/{id}/reset-password` | Geçici parola üret; refresh token revoke |
| B11 | `get_current_user` güncelleme | DB'den is_active, is_deleted, club_id, role kontrolü → 401 (G2) |
| B12 | `membership_approval.py` refactor | user_account_service kullanımına geçiş |
| B13 | `POST /users/{id}/restore` | Soft-delete geri alma; silinmiş hesabın e-postasıyla yeni hesap yerine restore kullanılır (G9) |

## Frontend Eksikleri

| # | Eksik | Açıklama |
|---|---|---|
| F1 | `api/users.ts` | API istemci fonksiyonları (restore dahil) |
| F2 | `pages/users/UsersPage.tsx` | Kullanıcı listesi (rol, aktiflik filtresi) |
| F3 | `pages/users/UserFormModal.tsx` | Oluşturma / düzenleme |
| F4 | Geçici parola gösterimi | Oluşturma/reset sonrası tek seferlik modal |
| F5 | Aktif/pasif/restore toggle | Kullanıcı durumu yönetimi |
| F6 | Parola reset aksiyonu | "Geçici parola oluştur" butonu |
| F7 | Person seçici | Yalnızca aktif + rol uyumlu Person'lar |
| F8 | Sidebar/nav bağlantısı | `/kullaniciler` menüsü |
| F9 | 401/403 ayrımı | 401 → session-expired logout, 403 → yetki hatası mesajı (logout değil) |
| F10 | `/auth/me` Person→User | must_change_password artık User'dan okunacak |

---

## İmplementasyon Sırası (Bağımlılık Zinciri)

```
AŞAMA 0 — Production veri denetimi (P0)
  [P0] Salt-okunur 7 sorgu                 ← bağımsız; tüm M'ler bunu bekler

AŞAMA 1 — Migration + ORM (P0 sonrası)
  [M3] Migration 0019 + test_migration_0019.py  ← P0 tamamlanınca

AŞAMA 2 — Schema + Servis (M3 sonrası)
  [M2] schemas/user.py                     ← M3 tamamlanınca
  [M5] get_current_user DB kontrolü + test ← M3 ile paralel
  [M9] /auth/me must_change_password fix   ← M3 tamamlanınca

AŞAMA 3 — Ortak Servis (M2+M3 sonrası)
  [M1] user_account_service.py + testler   ← M2, M3 tamamlanınca

AŞAMA 4 — Router (M1+M2+M3 sonrası)
  [M4] routers/users.py + testler         ← M1, M2, M3 tamamlanınca
  [M7] main.py router include             ← M4 tamamlanınca
  [M6] membership_approval.py refactor    ← M1 tamamlanınca

AŞAMA 5 — Frontend (M7 sonrası)
  [M8] api/users.ts                       ← M7 tamamlanınca
  [M10] UsersPage.tsx + UserFormModal.tsx ← M8 tamamlanınca
  [M11] Sidebar/nav güncelleme            ← M10 tamamlanınca

AŞAMA 6 — UAT ve Release
  [M12] Entegrasyon test kapsamı doğrula  ← M7 + M11 tamamlanınca
  [M13] UAT + v0.24.0 tag                 ← M12 geçtikten sonra
```

**Her backend task kendi testleriyle birlikte teslim edilir.**

---

## Test Senaryoları (UAT Kriterleri)

| # | Senaryo | Beklenen |
|---|---|---|
| T1 | Aktif sporcu kaydına User oluştur | 201, geçici parola döner (tek seferlik) |
| T2 | Pasif / başka kulüp kişisine User | 422 / 404 |
| T3 | Aynı person_id'ye ikinci User | 409 Conflict |
| T4 | Rol uyumsuz ata (sporcu rolü + antrenor PersonRole) | 422 |
| T5 | Pasifleştir → tüm refresh token'lar revoke | Login başarısız |
| T6 | Pasifleştir → mevcut JWT ile istek | 403 Forbidden |
| T7 | Son yöneticiyi sil/pasifleştir | 409 Conflict |
| T8 | Kendi hesabını sil | 403 Forbidden |
| T9 | Parola reset → geçici parola ile giriş | 200, must_change_password=true |
| T10 | İlk giriş → ChangePasswordPage → dashboard | Yönlendirme çalışır |
| T11 | sporcu rolüyle Katılım ekranı | 200 |
| T12 | sporcu rolüyle başka sporcunun verisi | 403 |
| T13 | Tenant izolasyon — başka kulüp user ID | 404 |

---

## Kapsam Dışı (Bu Sprint)

- SMTP / e-posta daveti (HTTPS sonrası)
- `token_version` (JWT revoke için; is_active kontrolü bu sprint için yeterli)
- Person.must_change_password kaldırma (Migration 0020 — sonraki sprint)
- OAuth / SSO
- Bulk kullanıcı import
- HTTPS (release gate — geliştirme/UAT IP üzerinden devam eder)

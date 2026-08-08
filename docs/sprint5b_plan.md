# Sprint 5B — Plan

**Önceki:** Sprint 5A ✅ PASS (v0.5.5, 2026-08-08)  
**Bu Sprint:** Üyelik portalı frontend + açık maddeler

---

## Sprint 5A'dan Devreden Açık Maddeler

| Madde | Öncelik | Not |
|-------|---------|-----|
| `member_number` API yanıtına ekle | Yüksek | Şu an yalnızca DB'de görünüyor |
| `must_change_password` first-login akışı | Orta | İş kuralı kararı gerekiyor — flag `false` geliyor |
| Veli-sporcu ilişkilendirme | Orta | Sprint 5A scope'undaydı, uygulanmadı |
| SMTP production yapılandırması | Düşük | Şu an log-mode; DNS + e-posta sağlayıcı gerekiyor |

---

## Sprint 5B Kapsamı

### 1. Backend — Küçük düzeltmeler

**1a. `member_number` API'ye ekle**  
`PersonOut` schema'sına `member_number: str | None` alanı ekle.  
Migration gerektirmez, model alanı zaten var.

**1b. `must_change_password` iş kuralı kararı**  
Seçenekler:
- A) Login yanıtına `must_change_password` flag ekle → frontend force-redirect uygular
- B) Şimdilik skip — kullanıcıya temp password e-postayla gönderildiği için ilk girişte değiştirmesi yönlendirilir

**1c. Veli-sporcu ilişkilendirme**  
`guardian_name` / `guardian_phone` başvuruda var → onayda Person'a aktarılıyor mu kontrol et.  
Ayrı `PersonGuardian` ilişkisi gerekiyorsa migration 0006.

---

### 2. Frontend — Üyelik yönetimi ekranları

**2a. Başvuru listesi (`/admin/applications`)**
- Tablo: ad, soyad, başvuru no, tarih, durum badge
- Filtre: status (submitted / approved / rejected)
- Satıra tıklayınca detay

**2b. Başvuru detay + onay/red (`/admin/applications/:id`)**
- Tüm başvuru alanları
- "Onayla" / "Reddet" / "Revizyon İste" butonları
- Red için reason input
- Onay sonrası person_id + member_number göster

**2c. Dashboard badge güncellemesi**
- `bekleyen_basvuru` sayacı zaten API'den geliyor
- Sidebar'da canlı badge ekle

**2d. Public başvuru formu (`/basvuru`)**
- Auth gerektirmez
- KVKK onay checkbox zorunlu
- Başarı sayfası: "Başvurunuz alındı, başvuru no: MYK-2026-NNNNNN"

---

### 3. Ertelenen (Sprint 5C)

- Flask LMS → FastAPI SSO/JWT entegrasyonu (mimari analiz önce)
- Deniz Akademisi tam entegrasyonu
- Alan adı + HTTPS (DNS hazır olunca)

---

## Execution Order

```
1. member_number API fix  (backend, migration yok, hızlı)
2. must_change_password karar + uygulama
3. Veli ilişkilendirme analiz (migration 0006 gerekiyorsa)
4. Frontend: başvuru listesi
5. Frontend: başvuru detay + onay/red akışı
6. Frontend: public başvuru formu
7. Dashboard badge
8. v0.6.0 tag
```

---

## Hazır Olma Kriterleri

- [ ] `member_number` `/api/v1/persons/:id` yanıtında görünüyor
- [ ] Başvuru listesi ve detay ekranı yönetici panelinde çalışıyor
- [ ] Onay/red akışı portal üzerinden yapılabiliyor (API curl yerine UI)
- [ ] Public başvuru formu `/basvuru` URL'sinde erişilebilir
- [ ] Dashboard sidebar'da `bekleyen_basvuru` badge görünüyor
- [ ] 130+ test hâlâ yeşil

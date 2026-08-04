# MYK Platform — Önerilen Prosedür Listesi
**Faz 1 Çıktısı · 2026-07-30**

---

## 1. Kapsam

Bu liste, MYK Platform V2 çerçevesinde yazılım davranışını doğrudan etkileyen prosedürleri tanımlar. Her prosedür: bir tetikleyici olay, iş akışı adımları ve sorumlu rol içerir. El Kitabı dokümanları bu prosedürlerin yazılı referansıdır.

---

## A. Üye & Sporcu Prosedürleri

### PRO-A-001: Yeni Üye Kaydı
**Tetikleyici:** Üye başvurusu  
**Akış:** Başvuru formu → Yönetici inceleme → Onay/Red → Kulüp sistemi kaydı → Aidat planı oluşturma → Bildirim  
**Sorumlu:** Yönetici  
**El Kitabı:** MYK-MEM-001  
**Sistem:** `/api/kullanicilar` POST

### PRO-A-002: Sporcu Profili Güncelleme (Sağlık Bilgisi)
**Tetikleyici:** Vizesi biten sporcu, sağlık değişikliği  
**Akış:** Sporcu/veli form girer → Antrenör/yönetici doğrular → Hassas alan log kaydı → Bildirim  
**Sorumlu:** Antrenör veya Yönetici  
**Güvenlik notu:** TC kimlik ve sağlık alanları şifreli, muhasebe/personel/antrenör maskeleri  
**Sistem:** `/api/sporcular/<id>` PUT

### PRO-A-003: Veli Atama
**Tetikleyici:** Reşit olmayan sporcu kaydı  
**Akış:** Sporcu oluştur → Veli kullanıcı oluştur → İlişki bağla → Veli scope doğrula  
**Sorumlu:** Yönetici  
**Sistem:** `/api/veli-sporcu` POST

---

## B. Eğitim Prosedürleri

### PRO-B-001: Kurs Oluşturma
**Tetikleyici:** Yeni eğitim dönemi  
**Akış:** Kurs tanımla (başlangıç/bitiş, kapasite, ücret, müfredat seviyesi) → Onay → Kayıta aç  
**Sorumlu:** Sportif Direktör veya Yönetici  
**El Kitabı:** MYK-CILT-003, MYK-COA-001  
**Sistem:** `/api/kurslar` POST

### PRO-B-002: Kursa Kayıt
**Tetikleyici:** Sporcu/veli başvurusu  
**Akış:** Müsait yer kontrolü → Ödeme planı → Kayıt oluştur → Bildirim → Devam listesine ekle  
**Sorumlu:** Yönetici veya sistem otomatik  
**Sistem:** `/api/kayitlar` POST

### PRO-B-003: Yoklama Kaydı
**Tetikleyici:** Günlük ders  
**Akış:** Antrenör listeden yoklama işler → Sistem kaydeder → Devamsızlık uyarısı eşiği aşılırsa bildirim  
**Sorumlu:** Antrenör  
**Sistem:** `/api/yoklama` POST

### PRO-B-004: Ders İçeriği Yayımı (KnotPlayer)
**Tetikleyici:** Yeni bağ veya teknik içerik ekleme  
**Akış:** Timeline JSON hazırla → `validate_knot_timelines.py` çalıştır → Yönetici onayı → Sisteme ekle  
**Sorumlu:** Sportif Direktör veya Antrenör + Teknik  
**Sistem:** `static/knots/<slug>/timeline.json`

---

## C. Deniz Operasyonları Prosedürleri

### PRO-C-001: Tekne Rezervasyonu
**Tetikleyici:** Kulüp üyesi/sporcu talebi  
**Akış:** Müsaitlik kontrolü → Rezervasyon oluştur → Deniz log ilişkilendir → Teslim/iade  
**Sorumlu:** Personel veya Yönetici  
**Sistem:** `/api/rezervasyonlar`

### PRO-C-002: Deniz Logu Kaydı
**Tetikleyici:** Denize çıkış  
**Akış:** Gemi, süre, personel, hava durumu, rota gir → İmzala → Arşivle  
**Sorumlu:** Personel/Antrenör  
**El Kitabı:** MYK-CILT-002  
**Sistem:** `/api/deniz-loglari` POST

### PRO-C-003: Ekipman Bakım Talebi
**Tetikleyici:** Periyodik takvim veya arıza bildirimi  
**Akış:** Arıza/bakım kaydı oluştur → Öncelik ata → İş emri → Tamamlandı işaretle → Maliyet kaydı  
**Sorumlu:** Personel  
**El Kitabı:** MYK-ASSET-001  
**Sistem:** `/api/ekipmanlar/<id>` PUT

### PRO-C-004: Destek Botu Görev Kaydı
**Tetikleyici:** Destek/kurtarma botu göreve çıkacak  
**Akış:** Görev oluştur → Yetkili personel ata → Ekipman kontrol listesi işle → Denize çıkış onayı (dijital) → Görev kaydı → Dönüş ve ekipman iade kaydı → Audit log  
**Sorumlu:** Yönetici veya Operasyon Sorumlusu  
**Yapılandırma:** Yetkili personel kriterleri, gerekli belgeler ve kontrol listesi içeriği sistem yöneticisi tarafından tanımlanır — sabit kodlanmaz.  
**CONFLICT-001 notu:** Yönetici aktif bot talimatını DMS'te belirler; seçilen talimata göre sistem yapılandırılır. Eski belgeler arşivde kalır.

---

## D. Doküman Yönetimi Prosedürleri

### PRO-D-001: Yeni Doküman Yükleme
**Tetikleyici:** Yönetici veya yetkili kullanıcı  
**Akış:** Dosya seç → Uzantı/MIME/magic bytes kontrolü → Meta veri gir (kod, revizyon, kategori) → Çakışma kontrolü → Yükle → Audit log  
**Güvenlik:** Extension whitelist, max 15MB, BLOCKED_EXTENSIONS reddi  
**Sistem:** `/api/belgeler/upload` POST

### PRO-D-002: Doküman Revizyon
**Tetikleyici:** Güncellenmiş versiyon hazır  
**Akış:** Yeni revizyon dosyası yükle → Eski revizyon "superseded" işaretle → Revizyon zinciri güncelle → Bildirim (değişiklik bildirimi gereken kullanıcılar)  
**Sistem:** `/api/belgeler/<id>/yeni-revizyon` POST

### PRO-D-003: Belge Import (Toplu)
**Tetikleyici:** Yeni belge paketi mevcut  
**Özel kurallar:**
- Dry-run zorunludur (--dry-run: belge oluşturulmaz, depolama değişmez)
- CONFLICT-001 → Yönetici önce DMS üzerinden aktif belgeyi seçmeli; seçim yapılmadan import uyarı verir ancak sert blokaj uygulanmaz (`force=True` engeli yoktur)
- Gerçek 317 belge import edilmemiş olmalı (üretim)
- Production DB doğrudan değiştirilemez
**Sistem:** `scripts/import_docs.py`

### PRO-D-004: Uygunsuzluk Kaydı
**Tetikleyici:** Denetim, kullanıcı bildirimi veya sistem anomali tespiti  
**Akış:** Uygunsuzluk kaydı aç → Kategori/önem ata → Düzeltici faaliyet planla → Kapat → Audit  
**El Kitabı:** MYK-AUDIT-001  
**Sistem:** `/api/uygunsuzluklar`

---

## E. Erişim & Güvenlik Prosedürleri

### PRO-E-001: Kulüp İlk Kurulum
**Tetikleyici:** Yeni kulüp onboarding  
**Akış:** `/api/kurulum` POST → `yonetici` rolü oluştur → Secret key env var'larını ayarla → İlk kullanıcıyı giriş yaparak doğrula  
**Güvenlik notu:** `admin@myk.com`/`myk2024` gibi sabit kimlik bilgileri KULLANILMAZ  
**Sistem:** `/api/kurulum`

### PRO-E-002: Şüpheli Giriş Kilidi Kaldırma
**Tetikleyici:** Brute-force kilidi sonrası meşru kullanıcı  
**Akış:** Rate limit süresi bekle VEYA Redis anahtarını yönetici konsoldan sıfırla  
**Sorumlu:** Sistem yöneticisi  
**Sistem:** Redis key `rl:{kulup_slug}:{email}:{ip}`

### PRO-E-003: Rol Değişikliği
**Tetikleyici:** Personel değişikliği  
**Akış:** Yönetici onayı → Kullanıcı rol güncelle → Audit log → Yeni izinler anında yürürlüğe girer  
**Sorumlu:** Yönetici  
**Sistem:** `/api/kullanicilar/<id>` PUT

---

*Prosedürler El Kitabı dokümanları ve mevcut yazılım API'si analiz edilerek oluşturulmuştur.*

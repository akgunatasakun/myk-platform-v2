# MYK Platform V2 — Risk Listesi
**Faz 1 Çıktısı · 2026-07-30**

---

## Değerlendirme Ölçeği

| Olasılık | Etki | Risk Seviyesi |
|---|---|---|
| Yüksek × Yüksek | KRİTİK | 🔴 |
| Yüksek × Orta / Orta × Yüksek | YÜKSEK | 🟠 |
| Orta × Orta | ORTA | 🟡 |
| Düşük veya Etki düşük | DÜŞÜK | 🟢 |

---

## R01 — Bot Talimatı İç Tutarsızlığı 🟡

**Kategori:** İç Doküman Standardizasyonu  
**Açıklama:** Kulübün dört farklı destek/kurtarma botu talimatı mevcuttur. Personel yeterliliği ve görev ataması bakımından farklılık içermektedir.  
**Risk:** Yönetici hangisinin geçerli olduğunu sisteme bildirmezse yazılım yanlış kural uygulayabilir.  
**Azaltma:** Yönetici aktif talimatı DMS'te seçer; sistem bu seçime göre yapılandırılır. Yetkili personel kriterleri ve kontrol listeleri sabit kodlanmaz — yönetici arayüzden tanımlar. Hukuki blokaj veya Liman Başkanlığı onayı gerekmez.  
**Aşama 2 üzerindeki etkisi:** Yok. Aşama 2 başlayabilir.

---

## R02 — Kişisel Veri Sızıntısı 🔴

**Kategori:** Güvenlik & KVKK  
**Açıklama:** TC kimlik numarası, kan grubu, alerji, özel sağlık durumu, acil kişi bilgileri gibi hassas veriler sistemde tutulacak.  
**Risk:** DB sızıntısı, şifrelenmemiş yedek, log'a yazılan hassas alan → KVKK ihlali, idari para cezası, itibar kaybı.  
**Azaltma:** pgcrypto AES-256 ile alan şifreleme; loglara hassas alan yazılmaması; yedekler şifreli; penetrasyon testi MVP öncesi.

---

## R03 — Tek Kişi Bağımlılığı (Bus Factor) 🟠

**Kategori:** Proje Yönetimi  
**Açıklama:** Geliştirme sürecinin tek geliştirici veya tek AI oturumu üzerinden yürütülmesi.  
**Risk:** Bağlam kaybolursa (oturum sıfırlanma, vb.) mimari kararlar ve önceki sprintlerin birikimi erişilemez olabilir.  
**Azaltma:** Her faz sonunda Git commit + tag; ARCHITECTURE.md ve CHANGELOG.md güncel tutulmalı; kritik kararlar ADR'lerle belgelenmeli.

---

## R04 — SQLite → PostgreSQL Veri Taşıma Riski 🟠

**Kategori:** Teknik  
**Açıklama:** Mevcut MYK_Yazilim'de SQLite ile üretilen test ve pilot verilerinin PostgreSQL'e taşınması.  
**Risk:** Tip uyumsuzluğu (INTEGER PK → UUID, TEXT tarih → TIMESTAMPTZ), karakter seti sorunu, JSON→JSONB dönüşüm hatası.  
**Azaltma:** Migration script'i test ortamında çalıştırılmadan production'a dokunulmamalı; migration sonrası satır sayısı ve checksum doğrulaması yapılmalı.

---

## R05 — Doküman Kaosunun Yazılıma Yansıması 🟠

**Kategori:** İş Analizi  
**Açıklama:** 256 taslak dokümanın konsolidasyonu tamamlanmadan modüller kodlanırsa iş kuralları yanlış veya eksik uygulanabilir.  
**Risk:** Sonradan ortaya çıkan prosedür çelişkileri kodu yeniden yazmayı gerektirebilir.  
**Azaltma:** Her modül için bağlı prosedür dokümanı belirlenmeli; prosedür "yürürlükte" statüsüne gelmeden o modülün kabul testi geçemez.

---

## R06 — Frontend Güvenlik Kontrollerini Yeterli Saymak 🟠

**Kategori:** Güvenlik  
**Açıklama:** "Butonu gizle" veya "route'u kaldır" yaklaşımı gerçek erişim kontrolü sağlamaz.  
**Risk:** API doğrudan çağrılırsa UI kontrolleri devre dışı kalır; yetkisiz işlem yapılabilir.  
**Azaltma:** Her API endpoint'inde `_has_perm()` + tenant filtresi zorunlu; frontend kontrolü yalnızca UX amaçlı.

---

## R07 — Docker / Production Ortam Farklılığı 🟡

**Kategori:** Teknik  
**Açıklama:** Geliştirme ortamı ile production ortamı arasında davranış farkı oluşabilir (volume path, env var, Redis bağlantısı).  
**Risk:** "Bende çalışıyor" durumu; production deploy'da beklenmedik hata.  
**Azaltma:** CI pipeline'da Docker Compose ile tam stack testi; `.env.example` eksiksiz tutulmalı; staging ortamı MVP öncesi kurulmalı.

---

## R08 — Yüksek Kapsam Kayması 🟡

**Kategori:** Proje Yönetimi  
**Açıklama:** 6 modül için tanımlanan MVP, her aşamada büyüme eğilimi gösterebilir (yarış modülü, hava entegrasyonu, MFA...).  
**Risk:** MVP hiç teslim edilemez; kaynaklar tükenir.  
**Azaltma:** MVP sınırı sabit tutulmalı; istekler backlog'a alınmalı; "şimdi değil, Faz 2" kararı tek sorumlu tarafından verilmeli.

---

## R09 — AI Ajan Hatalı Öneri 🟡

**Kategori:** Sistem Güvenilirliği  
**Açıklama:** Kural motorunun eksik veya hatalı veriyle çalışması yanlış uyarı üretebilir.  
**Risk:** Yanlış "engel" kararı operasyonu durdurabilir; yanlış "güvenli" kararı gerçek sorunu gizleyebilir.  
**Azaltma:** Ajan Seviye 3 (LLM) sonuçlarını her zaman "öneri" olarak sun; kritik kayıtlara dokunma için insan onayı zorunlu; tüm ajan aksiyonları audit_log'a yazılsın.

---

## R10 — Çok Kiracılı Mimari İzolasyon Hatası 🟡

**Kategori:** Güvenlik  
**Açıklama:** Yanlış yazılan bir sorgu `club_id` filtresi olmadan çalışabilir.  
**Risk:** Bir kulübün kullanıcısı başka kulübün verisine erişir.  
**Azaltma:** Repository katmanında `club_id` parametresi zorunlu yapılmalı; tenant izolasyon test suite her deployment'ta çalıştırılmalı.

---

## R11 — E-posta / SMS / WhatsApp Entegrasyonu Gecikmesi 🟢

**Kategori:** Özellik Riski  
**Açıklama:** Bildirim kanalları için dış sağlayıcı sözleşmesi ve API anahtarı gerekmektedir.  
**Azaltma:** MVP'de soyutlama katmanı hazırlanır, gerçek bağlantı Faz 2'de eklenir. Mock provider ile test edilebilir.

---

## R12 — Vize / Lisans Kontrol Yanlışlığı 🟢

**Kategori:** İş Riski  
**Açıklama:** Sporcu vizeleri TYF sistemindeki veriye bağlı; el ile girilirse hata yapılabilir.  
**Azaltma:** TYF API entegrasyonu Faz 2'ye planlanmış; MVP'de manuel giriş + hatırlatıcı.

---

## Özet Tablo

| # | Risk | Seviye | Faz |
|---|---|---|---|
| R01 | Bot talimatı iç tutarsızlığı | 🟡 ORTA | Aşama 2 sırasında |
| R02 | Kişisel veri sızıntısı | 🔴 KRİTİK | MVP |
| R03 | Tek kişi bağımlılığı | 🟠 YÜKSEK | Sürekli |
| R04 | SQLite→PostgreSQL taşıma | 🟠 YÜKSEK | Faz 2 başı |
| R05 | Doküman kaosu yansıması | 🟠 YÜKSEK | Faz 2 |
| R06 | Frontend güvenlik yanılgısı | 🟠 YÜKSEK | MVP |
| R07 | Docker ortam farkı | 🟡 ORTA | MVP |
| R08 | Kapsam kayması | 🟡 ORTA | Sürekli |
| R09 | Ajan hatalı öneri | 🟡 ORTA | Faz 5 |
| R10 | Tenant izolasyon hatası | 🟡 ORTA | MVP |
| R11 | Bildirim entegrasyon gecikmesi | 🟢 DÜŞÜK | Faz 2 |
| R12 | Vize kontrol yanlışlığı | 🟢 DÜŞÜK | Faz 2 |

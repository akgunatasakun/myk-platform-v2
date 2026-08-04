# MYK Platform — Tekrar ve Çakışma Raporu
**Faz 1 Çıktısı · 2026-07-30 · Faz0_5 DUPLICATE_CONFLICT_REPORT.md genişletilmiş**

---

## Özet

| Bulgu | Sayı |
|---|---|
| Klasörler arası aynı dosya tekrarı | 247 (root ⊆ El Kitaplari) |
| El Kitaplari içi aynı kod, farklı başlık | 48 kod |
| Prosedürler içi aynı kod, farklı başlık | 2 kod |
| CONFLICT-001 — Bot talimatı (iç prosedür çakışması) | 4 belge, yönetici aktif talimatı belirleyecek |
| Boyut alttoplamı (tekrar dosyalar) | ~9 MB (kaldırılabilir) |

---

## BÖLÜM 1: Klasörler Arası Tekrar

### 1.1 Root = El Kitaplari Altkümesi

Root klasöründeki **247 .docx dosyasının tamamı**, `MYK_El_Kitaplari_261_Cilt_Guncel_Paket/` klasöründe **aynı isimle** bulunmaktadır. El Kitaplari klasörü 9 ek dosya içermektedir.

**Eylem:** Root klasöründeki 247 dosya DMS'e import edilmemelidir. El Kitaplari tek kaynak olarak kullanılmalıdır.

### 1.2 El Kitaplari (R00) — Prosedürler (R01) Kapsama İlişkisi

39 ortak kodun El Kitaplari'nde R00 Taslak, Prosedürler'de R01 onaylı versiyonu mevcuttur.

**Eylem:** DMS'e her iki versiyon girilmelidir; R01 "aktif", R00 "arşiv/taslak" olarak işaretlenmelidir.

---

## BÖLÜM 2: Kod İçi Başlık Varyantları

Aynı belge kodunun birden fazla farklı başlıkla taslak versiyonu bulunmaktadır. Bu durum 48 kodda tespit edilmiştir. Örnekler:

### MYK-AUDIT-001 (3 varyant)
| Dosya | Başlık Farkı |
|---|---|
| MYK-AUDIT-001_Entegre_Ic_Denetim_ve_Uygunluk_Yonetimi... | Entegre + Uygunluk odaklı |
| MYK-AUDIT-001_Ic_Denetim_Guvence_ve_Kurumsal_Kontrol... | Güvence + İç Kontrol odaklı |
| MYK-AUDIT-001_Ic_Kontrol_Ic_Denetim_ve_Guvence... | İç Kontrol öncüllü |

### MYK-AUD-002 (3 varyant)
| Dosya | Başlık Farkı |
|---|---|
| ...Denetim_Uyum_Guvencesi_ve_Yonetim_Sistemi_Entegrasyonu | Entegrasyon odaklı |
| ...Performans_Oz_Degerlendirme_ve_Mukemmellik_Modeli | Öz değerlendirme odaklı |
| ...Yonetim_Gozden_Gecirme_ve_Kurumsal_Performans | Gözden geçirme odaklı |

### MYK-ASSET-001 (3 varyant)
| Dosya | Başlık Farkı |
|---|---|
| ...Varlik_Envanter_ve_Yasam_Dongusu_Yonetimi | Envanter vurgulu |
| ...Varlik_Yonetimi_ve_Yasam_Dongusu | Temel başlık |
| ...Varlik_Yonetimi_ve_Yasam_Dongusu_Yonetimi | Yönetim tekrarlı |

### Diğer Çok Varyantlı Kodlar
MYK-BCM-001, MYK-BCP-002, MYK-BRAND-001, MYK-BUSINESSCONTINUITY-001, MYK-CHANGE-001, MYK-COMP-001, MYK-COMPLIANCE-001, MYK-CONTINUITY-001, MYK-CRM-001, MYK-CSR-001, MYK-CUSTOMER-001, MYK-DATA-001, MYK-DIGITAL-001, MYK-DOC-001, MYK-DOCUMENT-001, MYK-ERM-002, MYK-ETHICS-001, MYK-EXC-001, MYK-EXCELLENCE-001, MYK-FACILITY-001, MYK-FUNDRAISING-001, MYK-GOV-002, MYK-GOVERNANCE-001, MYK-GOVERNANCE-002, MYK-GRC-001, MYK-IMS-001, MYK-INN-001...

**Eylem:** Her kod için R01 Prosedürler versiyonu varsa o önceliklidir. Yoksa El Kitaplari varyantları arasından yönetici seçim yapmalıdır. Seçilmeyen varyantlar "superseded" olarak arşivlenir.

---

## BÖLÜM 3: CONFLICT-001 — İç Doküman Standardizasyonu

📋 **YÖNETİCİ KARARI GEREKLİ — İÇ PROSEDÜR KONSOLİDASYONU**

Bu konu Faz0_5 raporunda tanımlanmıştır. **Hukuki bir engel değil**, kulübün dört farklı destek/kurtarma botu talimatından hangisinin güncel ve yürürlükte olduğunun belirlenmesi gereken iç doküman standardizasyon meselesidir.

### Konu: Destek Botu Personel Yeterliliği

| Belge | Revizyon | Kaynak |
|---|---|---|
| TYF 72/5 (2014) — destek-botu-kullanma-talimati-2015_r1.pdf | R1/2014 | TYF (resmi kaynak) |
| MYK Bot Talimatı (Kapsamlı) — MYK_Bot_Talimat.pdf | R01? | MYK |
| MYK Bot Talimatı 2026 — Mersin_Yelken_Kulubu_Destek_Kurtarma_Botu_Talimati_2026.pdf | 2026 | MYK |
| MYK Bot Talimatı (Kısa) — mersin_yelken_kulubu_bot_talimati.pdf | ? | MYK |

### Çakışan Madde

| | Eski 3 Belge | 2026 Belgesi |
|---|---|---|
| **Personel yeterliliği** | ADB yeterli ve kesin kulüp zorunluluğu | ADB asgari şart; ek yeterlilik kulüp yöneticisi kararına bırakıldı |
| **Durum** | Eski iç prosedür sürümü | Güncel iç prosedür sürümü |

### Önerilen Çözüm

```
1. Yönetici, dört belge arasından kulübün uyguladığı mevcut prosedürü
   belirler ve "aktif" olarak işaretler.
2. Diğer üç belge "superseded/arşiv" statüsüne alınır.
3. Aktif talimat, V2 sistemindeki bot operasyon modülünün yapılandırma
   kurallarına dayanak oluşturur.
4. Gelecekte prosedür güncellenirse revizyon zinciri DMS'te tutulur.
```

**V2 davranışı:** CONFLICT-001 için `force=True` dahil geçilemez sert blokaj uygulanmaz. Yönetici hangi belgenin aktif olduğunu sistem üzerinden seçebilir; eski belgeler arşivlenir. Bot operasyon modülü kilitlenmez.

---

## BÖLÜM 4: Prosedürler İçi Varyantlar

### MYK-COMP-001 (2 varyant)
- `MYK-COMP-001_Kurumsal_Uyum_Compliance_El_Kitabi_R01.docx`
- `MYK-COMP-001_Kurumsal_Uyum_El_Kitabi_R01.docx`

### MYK-CONT-001 (2 varyant)
- `MYK-CONT-001_Ic_Kontrol_El_Kitabi_R01.docx`
- `MYK-CONT-001_Ic_Kontrol_Sistemi_El_Kitabi_R01.docx`

**Eylem:** Bu iki grupta da yönetici hangi dosyanın aktif olduğuna karar vermelidir.

---

## BÖLÜM 5: Tarihsel Birikime Bağlı Tekrar Analizi

Taslak (R00) dosyaların çokluğu, belge üretim sürecinin ardışık iyileştirme döngülerini yansıtmaktadır. Bu varyantlar kasıtlı olarak üretilmiş olup içerik düzeltmelerini veya kapsam farklılıklarını temsil eder. Toplu silme yapılmamalı; her grup için yönetici onayıyla "kazanan" belirlenmeli ve diğerleri "superseded" olarak DMS'e girilmelidir.

---

## Eylem Özeti

| # | Eylem | Sorumlu | Aciliyet |
|---|---|---|---|
| E1 | Root 247 dosyayı DMS import dışı bırak | Teknik | Yüksek |
| E2 | CONFLICT-001: Yönetici aktif bot talimatını seçsin, diğerlerini arşivlesin | Yönetici | Orta |
| E3 | 48 kod için varyant seçimi (yönetici onayı) | Yönetici | Orta |
| E4 | MYK-COMP-001 ve MYK-CONT-001 varyant seçimi | Yönetici | Orta |
| E5 | Seçilen aktif talimatı DMS'e not ekleyerek kaydet | Yönetici | Orta |

---

*Faz0_5 DUPLICATE_CONFLICT_REPORT.md (2026-07-28) temel alınarak güncellenmiştir. CONFLICT-001 hâlâ açıktır.*

# MYK Platform — Doküman Envanteri
**Faz 1 Çıktısı · 2026-07-30 · Faz0_5 verileri güncellenmiş**

---

## 1. Yönetici Özeti

Çalışma klasöründe üç farklı doküman katmanı tespit edilmiştir. Bu katmanlar aynı anda sistemde bulunmakta ve önemli çakışmalar içermektedir. Tüm R00 Taslak dosyalar sisteme aktarılmadan önce yönetici onayından geçirilmelidir.

---

## 2. Doküman Katmanları

### 2.1 Katman Haritası

```
Klasör                                   Revizyon  Dosya   Benzersiz Kod  Durum
──────────────────────────────────────   ────────  ──────  ─────────────  ──────────────────
MYK_El_Kitaplari_261_Cilt_Guncel_Paket   R00       256     162            Taslak (aktif çalışma)
Root klasörü (MYK-*.docx)                R00       247     158            Taslak (El Kitaplari altkümesi)
Prosedürler/                             R01       41      41             Yayımlanmış (onaylı)
Prosedürler/ (PDF)                       R01       40      40             Yayımlanmış (onaylı, PDF çifti)
```

**Kritik gözlem:**
- Root klasöründeki 247 dosya, El Kitaplari'nin **bire bir altkümesidir** (0 farklı dosya).
- El Kitaplari, root'a ek olarak 9 dosya içerir (toplam 256).
- Prosedürler klasörü, 41 kodun **R01 onaylı versiyonlarını** içerir; bu kodların R00 taslakları da El Kitaplari'nde mevcuttur (39 ortak kod).

### 2.2 Gerçek Yayımlanmış Dokümanlar (Root PDF'ler)

Klasör kökünde bulunan aşağıdaki PDF'ler yayımlanmış ve kullanımda olan dokümanları temsil eder:

| Kod | Dosya | Sayfa | Konu |
|---|---|---|---|
| MYK-CILT-001 | MYK_Cilt1_Kurumsal_Yonetim_El_Kitabi.pdf | 16 | Kurumsal Yönetim |
| MYK-CILT-002 | MYK_Cilt2_Deniz_Operasyonlari_El_Kitabi.pdf | 15 | Deniz Operasyonları |
| MYK-CILT-003 | MYK_Cilt3_Egitim_El_Kitabi.pdf | 15 | Eğitim |
| MYK-CILT-004 | MYK_Cilt4_Yaris_Organizasyonu_El_Kitabi.pdf | 12 | Yarış Organizasyonu |
| MYK-CILT-005 | MYK_Cilt5_Kulup_Isletme_Mali_Yonetim_El_Kitabi.pdf | 12 | Mali Yönetim |
| MYK-CILT-006 | MYK_Cilt6_Uyelik_Topluluk_Yonetimi_El_Kitabi.pdf | 11 | Üyelik Yönetimi |
| MYK-CILT-007 | MYK_Cilt7_Iletisim_Pazarlama_Medya_El_Kitabi.pdf | 11 | İletişim |
| MYK-QMS-000 | MYK_QMS000_Ana_Yonetim_El_Kitabi.pdf | 10 | Ana Kalite El Kitabı |
| MYK-GOV-000 | MYK_GOV000_Kurumsal_Sart_Anayasa.pdf | 19 | Kurumsal Şart/Anayasa |
| TYF-YTE-D1 | D1-Egitim-Kitapcigi.pdf | 52 | D1 Yelken Eğitimi |
| TYF-YTE-D2 | D2-Egitim-Dokumani.pdf | 35 | D2 Yelken Eğitimi |
| TYF-YTE-D3 | D3-Egitim-Dokumani.pdf | 44 | D3 Yelken Eğitimi |
| TYF-US-001 | us-1-ucurtma-sorfu-egitim-dokumani.pdf | 20 | Uçurtma Sörfü Temel |
| TYF-US-002 | us-2-ucurtma-sorfu-egitim-dokumanii.pdf | 14 | Uçurtma Sörfü Gelişim |
| TYF-US-003 | us-3-ucurtma-sorfu-egitim-dokumanii.pdf | 11 | Uçurtma Sörfü İleri |
| MYK-WING-001 | Kanat_Sorfu_Egitim_ve_Yarisa_Hazirlik.pdf | 15 | Wing Foil Eğitim |

---

## 3. El Kitaplari (R00 Taslak) — Kategori Dağılımı

256 dosya, 162 benzersiz kod. Kategorilere göre:

| Kategori | Dosya Sayısı | Örnek Kod |
|---|---|---|
| Audit / Denetim | 6 | MYK-AUDIT-001, MYK-AUD-002 |
| Asset / Varlık | 5 | MYK-ASSET-001, MYK-AST-001 |
| BCM / İş Sürekliliği | 5 | MYK-BCM-001, MYK-BCP-002 |
| Compliance / Uyum | 5 | MYK-COMP-001, MYK-COMPLIANCE-001 |
| Change / Değişim | 5 | MYK-CHANGE-001 |
| Continuity | 5 | MYK-CONTINUITY-001 |
| Data / Veri | 5 | MYK-DATA-001 |
| Governance / Yönetişim | 5 | MYK-GOV-002, MYK-GOVERNANCE-001 |
| Innovation / İnovasyon | 9 | MYK-INN-001 |
| Knowledge | 9 | MYK-KNOWLEDGE-001 |
| Sustainability | 6 | MYK-SUS-001 |
| CRM / Üye İlişkileri | 4 | MYK-CRM-001 |
| Risk | 4 | MYK-RISK-001 |
| Strategy / Strateji | 3 | MYK-STR-001 |
| PMO | 3 | MYK-PMO-001 |
| Quality / Kalite | 3 | MYK-QMS-001 |
| Diğer (40+ kategori) | ~130 | ... |

### 3.1 Sistem Modülü ile Eşleşme

| Modül | El Kitabı Kodu(ları) | Platform Modülü |
|---|---|---|
| Sporcu & Üyelik | MYK-ATH-001, MYK-MEM-001 | sporcular, kayitlar |
| Finansal | MYK-BUD-001, MYK-FIN-001 | odemeler |
| Varlık & Ekipman | MYK-ASSET-001, MYK-AST-001 | ekipmanlar |
| Denetim & Uyum | MYK-AUDIT-001, MYK-COMP-001 | audit_log, uygunsuzluklar |
| Eğitim | MYK-COA-001, MYK-CILT-003 | kurslar, akademi |
| Deniz Operasyonları | MYK-CILT-002 | deniz_loglari |
| Yarış | MYK-ATH-001, MYK-CILT-004 | (Phase 2) yarış modülü |
| İletişim & Marka | MYK-COMMUNICATION-001, MYK-BRAND-001 | (Phase 2) bildirim |
| İnsan Kaynakları | MYK-HR-001, MYK-COA-001 | (Phase 2) personel |

---

## 4. Prosedürler (R01 Onaylı) — Tam Liste

41 benzersiz kod, her biri .docx + .pdf çifti olarak:

| Kod | Başlık Kısaltması |
|---|---|
| MYK-ARC-001 | Kurumsal Arşiv |
| MYK-ASSET-001 | Varlık Yaşam Döngüsü |
| MYK-ATH-001 | Sporcu Lisans Vize |
| MYK-AUD-002 | Kurumsal Denetim |
| MYK-AUDIT-001 | Entegre İç Denetim |
| MYK-BCM-001 | İş Sürekliliği |
| MYK-BCM-002 | Kurumsal Dayanıklılık |
| MYK-BEN-001 | Benchmarking |
| MYK-BRAND-001 | Marka Yönetimi |
| MYK-BSC-001 | Balanced Scorecard |
| MYK-BUD-001 | Bütçe Planlama |
| MYK-CHANGE-001 | Değişim Yönetimi |
| MYK-CMP-001 | Kamp Konaklama |
| MYK-COA-001 | Antrenör/Eğitmen |
| MYK-COM-001 | Komiteler |
| MYK-COMMUNICATION-001 | Kurumsal İletişim |
| MYK-COMMUNITY-001 | Toplumla İlişkiler |
| MYK-COMP-001 (x2) | Kurumsal Uyum (iki varyant) |
| MYK-COMPETENCY-001 | Yetkinlik Yönetimi |
| MYK-COMPLIANCE-001 | Mevzuat Uyum |
| MYK-CONT-001 (x2) | İç Kontrol (iki varyant) |
| MYK-CRISIS-001 | Kriz Yönetimi |
| MYK-CRM-001 | Üye İlişkileri CRM |
| MYK-CRM-002 | Üye Deneyimi |
| MYK-CSR-001 | Kurumsal Sosyal Sorumluluk |
| MYK-DATA-001 | Veri Yönetişimi |
| MYK-DEC-001 | YK Karar İzleme |
| MYK-DEN-001 | İç Denetim Uygunluk |
| MYK-DIGITAL-001 | Dijital Dönüşüm |
| MYK-DOC-001 | Doküman Kontrolü |
| + 11 ek | ... |

**Not:** MYK-COMP-001 ve MYK-CONT-001 kodlarında Prosedürler klasöründe de 2 varyant mevcut — kod standardizasyonu gerektirir.

---

## 5. DMS'e Aktarım Öncelikleri

Sisteme import edilecek belgeler için önerilen sıra:

| Öncelik | Belge Grubu | Revizyon | Adet | Açıklama |
|---|---|---|---|---|
| 1 | Cilt 1-7 PDF + QMS/GOV | R01 (PDF) | 9 | Yayımlanmış, bağlayıcı |
| 2 | TYF eğitim dokümanları | Güncel | 5 | Resmi kaynak |
| 3 | Prosedürler R01 | R01 | 41 | Onaylı prosedürler |
| 4 | El Kitaplari seçilmiş | R00 Taslak | ~50 | Yönetici onayı sonrası |
| ASKIDA | Bot talimatları (CONFLICT-001) | Çakışan | 4 | Yönetici aktif iç talimatı belirleyecek; diğer sürümler arşivlenecek |
| DIŞARIDA | Root tekrar dosyalar | R00 Taslak | 247 | El Kitaplari altkümesi — tekrar import edilmemeli |

---

*Bu envanter dosya sistemi analizi ve Faz0_5 DOCUMENT_MANIFEST.csv verileri temel alınarak hazırlanmıştır.*

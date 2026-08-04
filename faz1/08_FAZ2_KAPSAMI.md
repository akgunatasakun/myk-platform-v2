# MYK Platform V2 — Faz 2 Kapsamı
**Faz 1 Çıktısı · 2026-07-30**

---

## 1. Faz 2 Tanımı

Faz 2, MVP'nin kulüp operasyonlarında stabil çalıştığı doğrulandıktan sonra başlar. Faz 2, kulübün dışa dönük büyüme, rekabetçi spor ve kurumsal olgunluk ihtiyaçlarını karşılar.

**Faz 2 Ön Koşulları:**
- MVP 30 günlük production pilotu tamamlandı
- Kritik bug'lar yok
- CONFLICT-001 iç prosedür konsolidasyonu tamamlandı; sert blokaj bulunmaz, aktif talimat yönetici onayıyla seçildi
- Kullanıcı geri bildirimi toplandı

---

## 2. Faz 2 Modülleri

### 2.1 Yarış & Regatta Modülü

| Özellik | Açıklama |
|---|---|
| Yarış takvimi | Sezon planlaması, regatta takvimi |
| Sporcu seçimi | Regattaya kayıt, kadro oluşturma |
| Skiper & tekne eşleştirme | Performans verisi ile |
| Sonuç girişi | Puan hesaplama (RRS kuralları) |
| Performans analizi | Sporcu gelişim grafiği |
| TYF entegrasyonu | Lisans kontrolü, sonuç gönderimi |

**El Kitabı referansı:** MYK-CILT-004, MYK-ATH-001

### 2.2 MFA (Çok Faktörlü Kimlik Doğrulama)

| Özellik | Açıklama |
|---|---|
| TOTP kurulum | QR kod ile authenticator app bağlantısı |
| Giriş MFA adımı | 6 haneli TOTP kodu doğrulama |
| Yedek kodlar | 8 adet tek kullanımlık kurtarma kodu |
| Zorunlu MFA | Yönetici ve muhasebe rolleri için isteğe bağlı zorunlu |

### 2.3 Arka Plan Görev İşleme (Celery + Redis)

| Görev | Tetikleyici |
|---|---|
| Toplu belge dönüştürme (PDF→DOCX) | DMS yükleme |
| Gecikmiş ödeme bildirimi | Günlük tarama |
| Vize dolumu uyarıları | Haftalık tarama |
| Yedekleme | Gece otomatik |
| Rapor oluşturma | Kullanıcı talebi |

### 2.4 Push Notification & Bildirim Motoru

| Kanal | Kullanım |
|---|---|
| In-app bildirim | Yoklama hatırlatıcı, görev bildirimi |
| E-posta | Ödeme hatırlatıcısı, vize uyarısı |
| (Phase 3) SMS | Kritik güvenlik bildirimi |

### 2.5 Nesne Depolama (S3-Uyumlu)

MVP'deki yerel dosya sistemi, Faz 2'de S3-uyumlu nesne depolamayla (MinIO veya bulut sağlayıcı) değiştirilir.

| Faydası | Detay |
|---|---|
| Ölçeklenme | Dosya sistemi boyutu kısıtı kalkar |
| Yedekleme | Otomatik versiyonlama |
| CDN | Statik içerik hızlanması |
| Çok bölge | Felaket kurtarma |

### 2.6 Analytics & Raporlama Dashboard

| Rapor | Kitle |
|---|---|
| Üye büyüme trendi | Yönetici |
| Kurs doluluk oranı | Sportif Direktör |
| Ödeme ve gelir özeti | Muhasebe |
| Sporcu devam istatistiği | Antrenör |
| Ekipman kullanım raporu | Personel |
| AI ajan özet raporu | Yönetici |

### 2.7 Harici Entegrasyon

| Entegrasyon | Açıklama |
|---|---|
| TYF API | Lisans sorgulama, vize kontrolü |
| ISAF / World Sailing | Regatta sonuç gönderimi |
| Muhasebe yazılımı | Fatura export (isteğe bağlı) |
| Kamu e-posta gateway | Resmi yazışma |

### 2.8 Super Admin Yönetim Paneli

| Özellik | Açıklama |
|---|---|
| Çoklu kulüp listesi | Tüm tenant'ları göster |
| Plan yönetimi | Free / Pro / Enterprise geçişi |
| Sistem sağlık dashboard | Tüm kulüpler |
| Toplu işlemler | Bakım modu, migration |

### 2.9 Kamp & Konaklama

Sezon kampları, konaklama planlaması ve lojistik (MYK-CMP-001 referanslı).

---

## 3. Faz 2 → Faz 3 Geçiş Kriterleri

Faz 3 (belirsiz, uzun vadeli) için zemin:
- Mobil uygulama (React Native / PWA olgunlaşması)
- OpenData / sportif istatistik API'si
- AI ajan v2 (LLM + anomali tespiti birleşimi)
- Ulusal ölçek (çok kulüp SaaS pazarı)

---

*Kapsam, V2 gereksinim spesifikasyonu Faz 2 bölümü ve kulüp El Kitabı analizi temel alınarak hazırlanmıştır.*

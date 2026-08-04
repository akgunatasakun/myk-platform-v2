# MYK Platform — Ana Süreç Listesi
**Faz 1 Çıktısı · 2026-07-30**

---

## 1. Süreç Hiyerarşisi

MYK yelken kulübü operasyonları dört ana süreç ailesinde gruplandırılmıştır. Bu sınıflandırma hem El Kitabı içerikleri hem de mevcut yazılım modülleriyle örtüşmektedir.

```
MYK Ana Süreçleri
├── A. Üye & Sporcu Yönetimi
├── B. Eğitim & Akademi
├── C. Deniz Operasyonları
├── D. Kulüp Yönetimi & İdare
└── E. Kurumsal Destek Süreçleri
```

---

## A. Üye & Sporcu Yönetimi

| Kod | Süreç | Mevcut Modül | Öncelik |
|---|---|---|---|
| A.1 | Üyelik başvurusu ve kabulü | kullanicilar | MVP |
| A.2 | Üye profil yönetimi | kullanicilar | MVP |
| A.3 | Sporcu kaydı ve profil | sporcular | MVP |
| A.4 | Sağlık bilgisi ve vize takibi | sporcular | MVP |
| A.5 | Veli–sporcu ilişkisi yönetimi | veli_sporcu_iliskileri | MVP |
| A.6 | Lisans ve federasyon vizeleri | sporcular | MVP |
| A.7 | Üyelik aidatı takibi | odemeler | MVP |
| A.8 | Üye iletişim ve bildirim | — | Faz 2 |
| A.9 | Üye CRM & deneyim yönetimi | — | Faz 2 |

## B. Eğitim & Akademi

| Kod | Süreç | Mevcut Modül | Öncelik |
|---|---|---|---|
| B.1 | Kurs tanımlama ve planlama | kurslar | MVP |
| B.2 | Öğrenci kaydı (enrollment) | kayitlar | MVP |
| B.3 | Devam (yoklama) takibi | yoklama | MVP |
| B.4 | Eğitim ücret ve ödeme | odemeler | MVP |
| B.5 | Dijital ders içeriği (KnotPlayer) | akademi | MVP |
| B.6 | Öğrenci ilerleme takibi | akademi.ilerleme | MVP |
| B.7 | Antrenör/eğitmen yönetimi | kullanicilar (rol) | MVP |
| B.8 | D1/D2/D3 program müfredatı | — | Faz 2 |
| B.9 | Sertifikasyon ve başarı belgeleri | — | Faz 2 |
| B.10 | Yarış performans analizi | — | Faz 2 |

## C. Deniz Operasyonları

| Kod | Süreç | Mevcut Modül | Öncelik |
|---|---|---|---|
| C.1 | Tekne rezervasyonu | rezervasyonlar | MVP |
| C.2 | Deniz logu (görev kaydı) | deniz_loglari | MVP |
| C.3 | Tekne bakım planlaması | ekipmanlar | MVP |
| C.4 | Ekipman envanter yönetimi | ekipmanlar | MVP |
| C.5 | Destek botu operasyonları | — | MVP |
| C.6 | Güvenlik & acil müdahale | — | MVP |
| C.7 | Kamp / konaklama rezervasyonu | — | Faz 2 |
| C.8 | Yarış organizasyonu | — | Faz 2 |
| C.9 | Regatta yönetimi | — | Faz 2 |

## D. Kulüp Yönetimi & İdare

| Kod | Süreç | Mevcut Modül | Öncelik |
|---|---|---|---|
| D.1 | Kulüp kurulum ve konfigürasyon | /api/kurulum | MVP |
| D.2 | Kullanıcı ve rol yönetimi | kullanicilar | MVP |
| D.3 | Doküman yönetimi (DMS) | belgeler | MVP |
| D.4 | Doküman revizyon zinciri | doc_revizyonlar | MVP |
| D.5 | Uygunsuzluk takibi | uygunsuzluklar | MVP |
| D.6 | Audit log (değişiklik izleme) | audit_log | MVP |
| D.7 | Yönetim kurulu karar takibi | — | Faz 2 |
| D.8 | Komite yönetimi | — | Faz 2 |
| D.9 | Etkinlik planlama | etkinlikler | MVP |
| D.10 | Bütçe ve mali kontrol | — | Faz 2 |

## E. Kurumsal Destek Süreçleri

| Kod | Süreç | Mevcut Modül | Öncelik |
|---|---|---|---|
| E.1 | AI ajan çalıştırma | ajan | MVP |
| E.2 | Sistem yedekleme ve geri yükleme | scripts/backup.py | MVP |
| E.3 | Migration ve güncelleme | alembic | MVP |
| E.4 | Sağlık izleme | /api/health | MVP |
| E.5 | İç denetim ve uyum | — | Faz 2 |
| E.6 | Raporlama ve analitik | — | Faz 2 |
| E.7 | Entegrasyon (TYF, ISAF, harici) | — | Faz 2 |

---

## 2. Süreç Sahipliği

| Rol | Süreç Ailesi |
|---|---|
| Yönetici | A, B, C, D, E (tam) |
| Sportif Direktör | B, C (tam) + A (okuma) |
| Muhasebe | A.7, B.4, D.10 |
| Antrenör | B.1–B.10, C.1–C.2 |
| Personel | C.1–C.6, D.3 (okuma) |
| Veli | A (kendi sporcusu), B (kendi sporcusu) |
| Sporcu | A.2, B.2, C.1 (kendi) |

---

*Süreç listesi El Kitabı kategori analizi ve mevcut yazılım modülleri birleştirilerek oluşturulmuştur.*

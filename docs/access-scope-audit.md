# Erişim kapsamı kontrolü — 20 Kasım 2026

Bu çalışma API üzerinden liste, detay, uyarı ve özet verilerinin erişim kapsamını kontrol eder. Canlı hesaplarla tarayıcı kabul testi yapılmamıştır.

## Bulgular ve düzeltmeler

| Alan | Önce | Sonra |
| --- | --- | --- |
| Sporcu listesi / uyarıları / detay | Sporcu ve veli kendi kayıtları dışında aynı kulübün sporcularını okuyabiliyordu; antrenörün detay ve uyarı uçlarında atama sınırı eksikti | Sporcu yalnız kendisini, veli yalnız aktif bağlantılı sporcularını, antrenör/başantrenör yalnız atanmış eğitim kapsamını okur |
| Pasif veli ilişkisi | Eğitim ve ödeme yardımcıları pasif bağlantıyı da kabul ediyordu | Eğitim, ödeme, DMS ve sporcu okuması ortak aktif ilişki denetimini kullanır |
| Kişi ilişki uçları | Antrenör kapsam dışı kişinin veli/sporcu ilişkilerini sorgulayabiliyordu | Kişi kapsamı kontrol edilir; veli üzerinden dönen sporcular da antrenör kapsamına süzülür |
| Ana panel | Giriş yapmış tüm roller kulüp genelindeki finans özeti, kurs ve işlem geçmişini alabiliyordu | Her veri kaynağı kendi iznine göre süzülür; veli/sporcu/antrenör kursları kendi kapsamıyla sınırlıdır; işlem geçmişi audit:read gerektirir |

Kendi kaydı bulunmayan hesap boş kapsam alır. Ortak yardımcı kullanıcı kaydını kulüp, aktiflik ve silinme durumuyla doğrular. SQL filtreleri sayaçlara ve sayfalamaya uygulanır.

## Korunan belge matrisi

| Roller | Poliçe/sözleşme dosyaları | Yenileme kayıtları |
| --- | --- | --- |
| super_admin, kulup_yonetici, genel_sekreter | Yönetir | Yönetir |
| baskan, yk_uyesi | Okur/indirir | Okur |
| muhasebe | Erişemez | Okur |
| sportif_direktor, basantrenor, antrenor, personel, saglik_sorumlusu, guvenlik_operasyon, uye, sporcu, veli, misafir | Erişemez | Erişemez |

Ayrıntılı belge kuralları: [document-access.md](document-access.md). Kişisel evraklarda ayrıca kişiye ve evrak türüne göre erişim kontrolü vardır.

## Doğrulama

- Yeni testler düzeltme öncesinde kapsam dışı listeler/200 yanıtlarıyla başarısız oldu; düzeltme sonrasında başarılıdır.
- `tests/test_access_scope_audit.py`: olumlu ve olumsuz kapsam kontrolleri, veli bağlantısının iptali, ana panel veri sızıntısı ve izinli eğitimlerin korunması.
- `tests/test_document_access.py`: 16 rol için liste/detay/revizyon/indirme; kütüphane üzerinden kısıt aşma ve kapanmış yenileme kontrolleri.
- `tests/test_renewals.py`: yenileme rol matrisi ve dönem işlemleri.
- Veritabanı şeması değişmez; migration gerekmez.

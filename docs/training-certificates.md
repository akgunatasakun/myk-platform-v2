# Kulüp eğitim sertifikası kayıt takibi

## Akış

Eğitim ayrıntısı → Katılımcılar → Sertifika Kayıtları bağlantısı ilgili kurs ve katılımcıyı filtreler. Eğitim menüsündeki Sertifika Kayıtları ekranı tüm yetkili kapsamı listeler.

1. Yönetici veya genel sekreter eğitim katılımcısını seçip taslak açar.
2. Taslakta sertifika adı ve yönetim notu düzenlenir.
3. Yetkili kişi eğitim sonucunu kontrol ederek düzenleme tarihini ve varsa geçerlilik sonunu kaydeder. Bu adım otomatik MYK-SRT numarası verir ve katılımcı/kurs adını sabitler.
4. Düzenlenmiş kayıt değiştirilemez veya silinemez. Gerekçeli iptal geçmişte kalır; ardından aynı eğitim katılımcısı için yeni taslak açılabilir.

Bu modül kulübün sertifika kaydını takip eder; PDF belge üretimi, elektronik imza veya TYF/MEB/World Sailing sertifikasyon entegrasyonu içermez. Devam ve ödeme verilerinden otomatik yeterlilik/onay kararı çıkarmaz. Eğitim sonucu yetkili kişi tarafından kontrol edilir; uygulama için varsayımsal bir devam eşiği atanmaz.

## Yetki matrisi

| Roller | Okuma | Yönetme |
| --- | --- | --- |
| super_admin, kulup_yonetici, genel_sekreter | Tüm kulüp kayıtları, yönetim notları | Taslak, düzenleme kaydı, iptal, taslak silme |
| baskan, yk_uyesi, sportif_direktor | Kulüp kayıtları; yönetim notu hariç | Yok |
| antrenor, basantrenor | Atandığı kurslar; yönetim notu hariç | Yok |
| sporcu | Kendi düzenlenmiş/iptal edilmiş kayıtları | Yok |
| veli | Aktif veli ilişkisi bulunan sporcuların düzenlenmiş/iptal edilmiş kayıtları | Yok |
| uye, misafir, muhasebe, personel, saglik_sorumlusu, guvenlik_operasyon | Yok | Yok |

Liste, detay, CSV ve filtreler aynı kapsamı kullanır. Veli/sporcu taslak göremez. Pasif veli bağlantısı erişim sağlamaz. Üye hesabı, kişi profilinde başka türler bulunmasına dayanarak ek yetki kazanmaz.

## Veri ve doğrulama

- 0032 migration `training_certificates` tablosu, kontrol kısıtları, kulüp/numara benzersizliği ve aktif kayıt indeksi ekler; `myk_app` uygulama rolüne tablo izinleri verilir.
- Aynı kulüp ve eğitim katılımcısı için bir açık taslak/düzenlenmiş kayıt bulunabilir. Benzersizlik veritabanında korunur. Numara kulüp içinde benzersizdir.
- Düzenlenmiş kayıtlar, kurs/katılımcı arşivlendiğinde geçmişten kaybolmaz. Yeni kayıt veya düzenleme adımında silinmiş/iptal edilmiş eğitim ilişkileri kabul edilmez.
- İleri tarihli düzenleme ve düzenleme tarihinden önce geçerlilik sonu reddedilir. Süresi dolmuş görünümü İstanbul tarihine göre hesaplanır.
- CSV filtreden ve yetkiden çıkmaz; formül enjeksiyonuna karşı hücreler korunur. 10.000 kayıt üstü dışa aktarma filtre daraltmayı gerektirir.
- Durum değişiklikleri ve taslak silme denetim kaydına girer. Düzenleme/iptal sırasında satır kilidi tekrar düzenlemeyi engeller.
- Yeni özellik için canlıda gerçek kişilere örnek düzenlenmiş sertifika üretilmez.

## Test kapsamı

Yerel API testleri 16 rolü, taslak/düzenleme/iptal geçişlerini, değişmez kayıtları, isim sabitlemeyi, mükerrer taslağı, tenant ve ilişki sınırlarını, filtre/CSV/paginasyonu ve tarih doğrulamasını kapsar. PostgreSQL CI şema/uygulama izinlerini, gerçek benzersizlik kısıtını ve ileri/geri geçişi kontrol eder. Frontend testleri menü/rota matrisi ve URL filtrelerini kapsar.

Canlı rol hesaplarıyla tarayıcı kabul kontrolü dağıtım sonrasında ve ilgili test hesabına güvenli girişle yapılmalıdır.

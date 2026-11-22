# Canlı antrenör kontrolü — 22 Kasım 2026

Kullanıcının antrenör rolüne aldığı test hesabıyla güvenli giriş yapıldı. Parola kaydedilmedi. Kontrol sırasında üretim verisi veya hesap/kişi türleri değiştirilmedi.

## Gözlemler

- Panel antrenör rolünü gösterdi; yönetim/finans menüleri kapalıydı.
- `/users`, `/odemeler`, `/belgeler`, `/yenilemeler` sayfaları doğrudan açıldığında Erişim Reddedildi ekranı geldi.
- Kurs listesinde atanmış tek eğitim; kişi rehberinde kendi kartı ve bu eğitimin iki katılımcısı göründü.
- Eğitim ayrıntısında eğitim/oturum düzenleme ve silme, katılımcı ekleme/iptal ve tahsilat işlemleri görünmedi. Katılımcı parasal bilgileri gizliydi.
- Sertifika ekranında taslak oluşturma işlemi yoktu. Kayıt bulunmadığından gerçek bir sertifika ayrıntısı üzerinde canlı kapsam kontrolü yapılamadı.
- Kurs listesi, sunucuda yazma hakkı olmayan antrenöre Yeni Eğitim / Düzenle / Sil düğmelerini gösteriyordu. Kayıt değiştirmeden gözlemlendi; mevcut backend `egitim:write` kontrolleri incelendi.

## Düzeltme

- Kurs listesi ve ayrıntısı aynı olumlu yazma yetkisi listesini kullanır; antrenör, salt okunur diğer roller ve bilinmeyen rollerin işlem düğmeleri gizlenir.
- Kişi formundaki çoklu sınıflandırma Kişi Türleri; hesap formundaki tek erişim rolü Sistem Yetkisi olarak adlandırılır. Mevcut tür/yetki verileri ve backend matrisi değiştirilmez.
- Kişi kartından Sistem Yetkisini Yönet bağlantısı ilgili hesabın mevcut tek yetki formunu açar; yetkiyi ikinci bir formda değiştirmez.
- Hesap ve kişi ayrıntısı ekranlarında salt okunur rollerin kullanamayacağı değiştirme işlemleri gizlenir.
- Hesap formu mevcut uygulamanın giriş/seçim stillerine uyarlanır; etiketler alanlarla bağlanır.

Kişi türleri kulüp içindeki ilişkileri ifade eder; bir kişi birden fazla türde olabilir. Sisteme giriş yetkisi ayrı kullanıcı hesabının rolüyle yönetilir. Mevcut hesaba ait kişi türlerini değiştirmek hesabın erişim rolünü değiştirmez. Yeni hesap açılırken uygulamanın mevcut başlangıç rolü atama kuralı geçerlidir.

Canlı kontrol tarayıcıdaki okuma ve yönlendirme davranışını kapsar; üretimde veri değiştirici API denemesi yapılmadı. Sporcu ve veli canlı testleri ayrı hesaplarla devam etmelidir. Yeni arayüz düzeltmelerinin canlı kabul kontrolü dağıtım sonrasındadır.

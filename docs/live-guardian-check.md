# Canlı veli kontrolü — 22 Kasım 2026

v0.24.12 dağıtımı başarılı. Sporcu hesabında ödeme menüsünün kalktığı ve doğrudan ödeme rotasının 403 verdiği canlıda doğrulandı. Eski sekmeler kapatılarak güncel uygulama açıldı.

Veli hesabıyla güvenli giriş yapıldı; üretim kayıtları değiştirilmedi.

- Panel bağlı tek sporcu kapsamını gösterdi. Eğitim listesi üç kurs; açılan kursun katılımcı listesi yalnızca bağlı sporcuyu gösterdi. Eğitim/tahsilat yazma düğmeleri yoktu.
- Ödeme ekranı hatasız açıldı; yalnızca bağlı sporcuya ait iki ödeme ve salt okunur görünüm vardı.
- Sertifika listesinde bağlı sporcuya ait düzenlenmiş bir kayıt vardı; oluşturma/düzenleme işlemleri yoktu. Ayrıntı açma denemesi sonuç vermedi; ayrıntı kabul testi tamamlanmadı.
- Belgeler listesi boştu; yönetim poliçe/sözleşmeleri görünmedi. Hesap yönetimi ve yenilemeler doğrudan URL ile 403 verdi.
- Veli Kayıtları, kisi:read gerektiren yönetim kişi listesine istek atıp yüklenemedi hatası gösteriyordu.

Düzeltme veli menüsünü mevcut sporcu API'sinin own-scope desteğini kullanan Bağlı Sporcular ekranına taşır. Sporcu listesi/ayrıntı rotası veliye açılır; sunucu aktif veli ilişkisi ve kulüp sınırını uygulamaya devam eder. Yönetim veli listesi/ayrıntı rotası veliye kapatılır. Backend izni genişletilmez.

Yeni menünün dağıtım sonrası canlı kabul kontrolü bekliyor.

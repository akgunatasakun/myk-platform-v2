# Eğitim kaydı ve tahsilat bağlantısı

## Kullanım

- Eğitim ayrıntısı → Katılımcılar bölümünde tahsil edilen ve kalan tutar gösterilir. Yetkili yönetici, kalan tutar için Ödeme Kaydı Ekle düğmesini kullanabilir.
- Ödemeler bölümünde kişi seçildikten sonra Bağlı Eğitim Kaydı seçilebilir. Muhasebe bu seçim için yalnız finans yetkisiyle erişebilir.
- Önceden kaydedilmiş bir tahsilat düzenlenip eğitim kaydına bağlanabilir. Aynı tahsilatı yeniden oluşturmamak gerekir.
- Bağlantı kaldırılabilir veya aynı kişinin başka eğitim kaydına taşınabilir; değişiklik denetim kaydına girer.

## Hesaplama ve sınırlar

- Eşleştirme kişinin kimliğiyle değil belirli `training_enrollment_id` ile yapılır.
- Yalnız silinmemiş ve `paid` durumundaki bağlı ödemeler tahsil toplamına girer. `pending` ödemeler tahsilat sayılmaz.
- Özet her okumada hesaplanır; güncelleme, silme ve bağlantı değişiklikleri bir sonraki okumada yansır. Yarışabilecek bir ödeme durumu önbelleği yazılmaz.
- Kalan tutar güncel kurs ücreti eksi tahsil toplamıdır; en az sıfır gösterilir. Kurs ücreti değiştirilirse kalan tutar da değişir. Kişiye özel sözleşme bedeli/indirim ve iade hesabı bu değişikliğin kapsamında değildir.
- Ücret sıfırsa Ücretsiz; hiç bağlı kayıt yoksa Bağlı Kayıt Yok; sıfır tahsilat varsa Bekliyor; pozitif eksik tahsilat varsa Kısmi Ödendi; ücret karşılanmışsa Ödendi görünür.
- Eski tahsilatlar ve eski `training_enrollments.payment_status` değerleri otomatik eşleştirilmez, yeni özete kaynak olmaz.
- Banka/kart işlemi yapılmaz; yalnız kulübün tahsilat kaydı yönetilir.

## Yetki

Yazma için `odeme:write` gerekir. Başka kişiye veya kulübe ait eğitim kaydına bağlanamaz. Yeni bağlantı iptal/silinmiş kayıt veya silinmiş kurs için reddedilir. İptalden önce bağlanmış ödeme sonradan güncellenebilir veya bağlantısı kaldırılabilir; tahsilat geçmişi korunur.

Katılımcı listesinde parasal özet için `odeme:read` gerekir. Velinin listesi aktif bağlı sporcularıyla sınırlıdır. Antrenör ve ödeme okuma yetkisi olmayan diğer roller tutar/durum alamaz. Kişi listesi ve kayıt iptal/ekleme kontrolleri salt okunur eğitim ekranlarında çalıştırılmaz.

## Yayın

0031 migration `payments.training_enrollment_id` nullable FK ve indeks ekler. Mevcut veriler NULL kalır. PostgreSQL ileri/geri migration testi CI'da çalışır.

Canlıda yönetici ile eğitim ayrıntısı ve devam raporu açıldı. Yeni ödeme akışı yalnız yerel test verileriyle doğrulandı; canlıda tahsilat oluşturulmadı. Gerçek sporcu/veli/antrenör rollerinin tarayıcı kabul testi için ilgili test hesaplarına güvenli giriş gerekir. Mevcut Test Antrenor oturumunun rolü kulup_yonetici'dir.

Sertifika kaydı/üretimi mevcut uygulamada bulunmuyor ve bu değişiklikle eklenmiyor.

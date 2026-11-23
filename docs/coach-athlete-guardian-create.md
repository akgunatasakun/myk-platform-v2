# Antrenör sporcu ve veli kayıt akışı

Antrenör/başantrenör Sporcu Kayıtları ekranında Yeni Sporcu ile yalnızca sporcu türünde kişi oluşturabilir. Kayıt oluşturan kullanıcı sunucuda tutulur; antrenör kendi eklediği sporcuları ders atanmadan da listeleyebilir ve ayrıntısını okuyabilir. Mevcut atanmış kurs kapsamı korunur.

Sporcu ayrıntısındaki Veliler / Vasiler bölümünde, erişilebilen sporcuya mevcut aktif veli bağlanabilir veya yeni veli kartı ve bağlantısı tek transaction içinde oluşturulabilir. Mevcut veli araması en az üç karakter, en çok on sonuçla yalnızca aynı kulüpteki aktif veli kartlarından ad ve kısmi telefon döndürür. Genel kişi listesi erişimi genişlemez.

Yeni veli kartı kullanıcı hesabı oluşturmaz; varsa mevcut veli hesabının bağlı sporcu erişimi mevcut aktif veli ilişkisi kurallarını izler. Bağlantı kurulunca teslim alma ve bildirim seçimleri kaydedilir; açık KVKK/muvafakat onayı otomatik verilmez. Aynı bağlantı tekrar eklenemez; pasif/eski ilişki otomatik etkinleştirilmez. Bağlantı düzenleme/silme ile kişi/profil düzenleme ve kullanıcı hesabı açma antrenöre verilmez.

Migration 0033 persons.created_by_user_id alanını nullable FK ve indeks olarak ekler. Eski kayıtların alanı boş kalır; geriye dönük sahiplik atanmaz. Başka kulübe ait kayıtlar ve başka antrenörün kapsam dışı sporcuları erişime kapalı kalır.

Doğrulama: sporcu oluşturma, oluşturanın kapsamı, başka antrenör/kulüp engeli, mevcut veli araması, yeni veli+bağlantı, yetkisiz kişi türleri/hesap açma/düzenleme/silme ve migration ileri/geri geçiş testleri. Üretim kayıtları değiştirilmedi; canlı kabul testi dağıtım sonrasındadır.

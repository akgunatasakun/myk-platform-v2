# Sporcu ayrıntısı işlem görünürlüğü

Veli canlı testinde görünen Profil Düzenle ve Kişi Kartı düğmeleri mevcut backend yetkileriyle eşleştirilir. Profil oluşturma/düzenleme sadece sporcu:* yetkisine sahip yönetici ve sportif direktöre; kişi kartı bağlantısı sadece kisi:read yetkisine sahip yönetici, muhasebe ve antrenöre gösterilir. Boş profil ekranındaki ikinci oluşturma düğmesi ve modal açılışı da aynı izinle korunur.

Veli ve sporcu bağlı sporcu ayrıntısını okumaya devam eder. Backend izinleri, evrak yükleme akışı ve üretim kayıtları değişmez. Tüm roller, bilinmeyen/yüklenmeyen rol ve mevcut/eksik profil için gerçek işlem bileşeni test edilir. Canlı kabul kontrolü dağıtım sonrasındadır.

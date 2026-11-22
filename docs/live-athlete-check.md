# Canlı sporcu kontrolü — 22 Kasım 2026

UAT sporcu hesabı güvenli girişle açıldı; ilk parola değişikliği kullanıcı tarafından tamamlandı. Test sırasında üretim kayıtları ve hesap bağlantıları değiştirilmedi.

- Sporcu listesi yalnızca bağlı tek kişi kartını gösterdi. Test hesabının görünen adı ile bağlı kartın adı farklıydı; bağlantıya müdahale edilmedi.
- Eğitim listesinde tek eğitim, katılımcı ayrıntısında yalnızca bağlı kişi göründü. Oluşturma/düzenleme/silme ve tahsilat işlemleri yoktu.
- Hesap yönetimi ve yenilemeler doğrudan URL ile açıldığında 403 ekranına yönlendi.
- Belge listesi boştu; yönetim poliçesi ve sözleşmesi görünmedi.
- Sertifika listesi boştu; oluşturma işlemi yoktu. Gerçek kayıt bazında belge/sertifika kapsamı doğrulanamadı.
- Ödemeler menüsü sporcuya gösterildi ancak liste yükleme hatası verdi. Kaynak incelemesi backend odeme:read izninin sporcuda bulunmadığını doğruladı.

Düzeltme, ödeme menüsü ve rota izinlerini mevcut sunucu matrisiyle eşleştirir. Ödeme yazma düğmeleri yalnızca yönetici ve muhasebeye açıktır. Başkan ve veli okur; veli kapsamını sunucu bağlı sporcularla sınırlar. Backend izinleri genişletilmez.

Veli canlı testi henüz yapılmadı. Yeni arayüzün canlı kabul kontrolü dağıtım sonrasındadır.

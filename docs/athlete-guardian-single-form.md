# Tek formda sporcu ve veli kaydı

Sporcu Kayıtları → Yeni Sporcu formunda isteğe bağlı Veli Bilgileri bölümü bulunur. Kullanıcı Şimdilik veli ekleme, Mevcut veliyi seç veya Yeni veli oluştur seçebilir. Yeni veli için ad, soyad ve isteğe bağlı telefon/e-posta; bağlantı için yakınlık, birincil veli, teslim ve bildirim seçimleri girilir. Sonradan sporcu ayrıntısından veli ekleme korunur.

POST /persons/athlete-registration, sporcu kartını, isteğe bağlı yeni veli kartını ve bağlantıyı tek transaction içinde oluşturur. Veli hatalı, pasif, başka kulüpte, e-postası mükerrer veya yetkisizse sporcu da kaydedilmez. Her iki kart yalnızca ilgili kişi türünde oluşturulur; sistem hesabı veya muvafakat otomatik oluşmaz. Önceki kişi oluşturma API davranışı korunur.

Kayıt öncesi veli araması mevcut üç karakter/on sonuç/aynı kulüp/aktif veli ve kısmi telefon sınırlarıyla çalışır. Önceki antrenör kişi kapsamı değişmez. Migration gerekmez; 0033 üzerine çalışır.

Sunucu testleri velisiz, mevcut velili ve yeni velili kayıtları yönetici ve iki antrenör rolünde; geçersiz/başka kulüpteki veli ve yetkisiz rol/hesap isteklerinin kısmi kayıt bırakmamasını kapsar. Canlı kayıt oluşturulmadı; kabul testi dağıtım sonrasında.

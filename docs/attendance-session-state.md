# Yoklama oturum verileri ve kaydedilmemiş girişler

Kurs, oturum ve yoklama yüklemelerinde effect temizlendikten sonra gelen eski yanıtlar artık ekranı değiştirmez. Yeni seçimde önceki tablo ve hata durumu temizlenir; oturum yüklenirken seçim kapalıdır. Yükleme hatası ile kayıt hatası ayrıdır: kayıt başarısız olursa tablo, girişler ve tekrar kaydetme düğmesi korunur.

Yüklenen tablo ile güncel girişler karşılaştırılır. Eğitim veya oturum seçimi değişirken kaydedilmemiş giriş varsa vazgeçme onayı sorulur. Reddedilirse seçim ve tablo değişmez. Başarılı kayıt yeni karşılaştırma tabanıdır; başarısız kayıt girişleri kaydedilmiş saymaz. Durumu seçilmeden saat/not girilmiş satırların sessizce atlanması engellenir.

Sayfa yenileme ve sekme kapatma için beforeunload uyarısı eklenir. Bu, tarayıcının desteklediği standart uyarıdır; özellikle mobilde kesin veri kurtarma veya kalıcı taslak anlamına gelmez. Uygulama içindeki menü/geri/ileri navigasyonu için genel router engelleyicisi bu değişikliğin kapsamında değildir. Veriler tarayıcı depolamasına yazılmaz. Backend, yetki ve migration değişikliği yoktur.

Doğrulama: ters sırada tamamlanan iki oturum isteği, seçim değişimi/unmount sonrası geç hata ve yükleme bitişi, aktif istek hatası, temiz/kirli seçimde onay kabul ve ret senaryoları. Canlı kayıt üzerinde değişiklik yapılmadı.

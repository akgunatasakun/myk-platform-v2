# Panel sürüm güncelleme bildirimi

Önceki dağıtımlarda açık sekmeler eski arayüzü göstermeye devam ediyordu. Otomatik kayıt yerine uygulamanın yönettiği prompt güncellemesi kullanılır. Yeni worker hazır olduğunda Yeni sürüm hazır kartı, Güncelle ve Daha sonra seçenekleri görünür. Erteleme güncelleme bilgisini kaybetmez; küçük bir düğmeden tekrar açılır.

Güncelleme öncesi açık panel sekmelerindeki kaydedilmemiş bilgilerin kaybolabileceği açıklanır ve kullanıcı onayı alınır. Güncelleme etkinleşmesi aynı kapsamdaki diğer sekmeleri de etkileyebilir. Form kaydı veya veri silme yapılmaz. Yeni sürüm kontrolü ilk kayıt sonrasında, görünür sekmeye dönüşte, çevrimiçi olunca ve 15 dakikada bir yapılır; çevrimdışı/gizli/kurulum süren durumlar ve eşzamanlı istekler atlanır, kontroller en az bir dakika aralıklıdır.

Workbox mevcut precache temizleme davranışı korunur. API verisi veya kimlik bilgileri için yeni önbellek kuralı eklenmez. Backend ve kullanıcı yetkileri değişmez; migration yok. Mevcut eski sekmeler bu yeni kodu henüz çalıştırmadığından ilk geçişte bir kez kapatıp açmak gerekebilir. Sonraki sürümlerde prompt devrededir.

Kontroller: güncelleme yokken gizli bildirim, erteleme görünümü, kullanıcının reddinde güncelleme yapılmaması, hata/yeniden deneme, çevrimdışı/gizli/kurulum ve eşzamanlılık; üretim derlemesinde prompt worker ve tek kayıt yöntemi. Canlı worker geçişi iki farklı sürümle ayrıca doğrulanmalıdır.

Resmî kaynaklar:
- https://vite-pwa-org.netlify.app/guide/prompt-for-update
- https://vite-pwa-org.netlify.app/guide/periodic-sw-updates

Kurulu vite-plugin-pwa 0.21.2 istemci kodu da kontrol edildi. workbox-window mevcut kilitli 7.4.1 sürümüyle doğrudan geliştirme bağımlılığı olarak tanımlandı.

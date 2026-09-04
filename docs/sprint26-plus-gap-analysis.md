# Sprint 26+ Gap Analizi

## Sprint 26A sonrası açık kararlar

- Yaş verisi DB'ye yazılmaz; doğum tarihinden tamamlanmış yaş hesaplanır.
- Yarış/Optimist yaşı bu sprintte hesaplanmaz. TYF'nin ilgili yıl talimatı ve yaş ölçütü doğrulandıktan sonra ayrı alan/gösterim tasarlanır.
- `athlete_profiles.kvkk_consent` gibi mevcut tek kutulu alanlar yeni hukuki model kabul edilmez; geriye dönük uyumluluk için ayrıca ele alınır.

## 26B — KVKK ve veli evrak merkezi

Release gate: Kulübün avukatı veya KVKK danışmanı veri envanterini, hukuki sebepleri, metinleri ve saklama sürelerini onaylamalıdır.

- Aydınlatma metni ile açık rıza ayrı metin, ayrı sürüm ve ayrı beyan olmalıdır.
- Açık rıza gerekmeyen bir işleme şartında kullanıcıdan sahte/zorunlu rıza istenmez.
- Sağlık raporu ve sağlıkla ilgili içerikler özel nitelikli kişisel veri olarak sınıflandırılır.
- İspat kaydı: metin kimliği/sürümü, beyan türü, kişi, temsil edilen çocuk, zaman, IP, istemci ve geri çekme zamanı.
- Evrak türleri: sağlık raporu, veli izin belgesi, taahhütname, vesikalık fotoğraf, kimlik fotokopisi.
- Belge türüne göre rol bazlı görüntüleme/indirme; sağlık verisine en dar yetki.
- Her görüntüleme ve indirme audit'e yazılır.
- Dosya türü/boyutu, zararlı yazılım taraması, şifreli saklama ve süre sonunda silme/imha iş akışı gerekir.
- Velayet/temsil doğrulaması ve bir velinin yalnız bağlı çocuklarının belgelerine erişmesi zorunludur.

## Duyurular

- Tür: yarış, kamp, eğitim, genel, acil.
- Hedef: tüm kulüp, roller, belirli eğitim/kurs veya seçili kişiler.
- Taslak/yayında/arşiv, yayın başlangıç-bitiş zamanı, sabitleme, public/private görünürlük.
- Ek dosya/bağlantı ve portal içi okundu bilgisi.
- Bildirim sistemi duyuru kaydını dağıtır; duyuru ile teslimat kaydı ayrı kalır.

## Toplu mesaj

- Duyuru üstünden çalışmalı; serbest alıcı listesine kontrolsüz gönderim yapılmamalı.
- Rol/kurs hedefleme, alıcı önizlemesi ve toplam alıcı sayısı.
- Yetki, rate limit, tekrar gönderim koruması, teslimat sonucu ve audit.
- Operasyonel üyelik bildirimleri ile tanıtım/ticari iletiler ayrı sınıflandırılmalı.
- Tanıtım iletileri için onay/ret ve gerekiyorsa İYS süreci hukukçu tarafından doğrulanmalı.

## TYF entegrasyonu keşfi

- Resmî API, SFTP veya düzenli CSV sağlanıyor mu?
- Kimlik doğrulama, alan sözlüğü, veri sorumlusu/veri işleyen rolleri ve aktarım şartları nedir?
- Eşleştirme anahtarı lisans numarası mı; değişiklik/pasiflik nasıl iletiliyor?
- Güncelleme sıklığı, hata düzeltme ve mutabakat süreci nedir?
- İlk güvenli seçenek: önizlemeli, doğrulamalı ve audit'li CSV içe aktarma.

## Erişilebilir destek görevlisi

- İlk MVP otomatik değil manuel görevli/gönüllü ataması olmalı.
- Ziyaret tarihi, ihtiyaç notu, uygun görevli, kabul/ret ve bildirim.
- Sağlık/engel ayrıntısı yerine operasyon için gerekli en az veri gösterilmeli.
- Otomatik eşleştirme ancak yeterli kullanım verisi ve açık kurallar sonrası değerlendirilir.

## Mağaza ve sponsor alanı

- Mağaza ayrı epic: katalog, stok, ödeme, fatura, teslimat/kargo, iade ve tüketici süreçleri.
- İlk MVP çevrimiçi ödeme yerine katalog ve kulüpten teslim talebi olabilir.
- Çocuk odaklı public sitede davranışsal reklam ağı kullanılmaz.
- Kontrollü sponsor alanı: onaylı sponsor, logo, bağlantı, yayın dönemi ve audit.

## Misyon, vizyon ve kalite politikası

- Metinler yönetim kurulu onayı olmadan resmî politika olarak yayımlanmaz.
- Önerilen ifade: “çocuklar dahil tüm bireylere”.
- Erişilebilirlik taahhüdü ile kalite politikası ayrı başlıklarda sürümlenir.

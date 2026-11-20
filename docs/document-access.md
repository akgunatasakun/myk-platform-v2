# Poliçe ve sözleşme erişim matrisi

Bu matris yönetim belgeleri ve belge yenileme takibi içindir. Kişisel sporcu/veli evraklarının kendi kayıtlarına ilişkin izinleri ayrı kalır.

| Rol | Yönetim belge dosyası | Yenileme takibi |
| --- | --- | --- |
| super_admin | Yönetir | Yönetir |
| kulup_yonetici | Yönetir | Yönetir |
| genel_sekreter | Yönetir | Yönetir |
| baskan | Okur / indirir | Okur |
| yk_uyesi | Okur / indirir | Okur |
| muhasebe | Erişemez | Okur |
| sportif_direktor | Erişemez | Erişemez |
| basantrenor | Erişemez | Erişemez |
| antrenor | Erişemez | Erişemez |
| personel | Erişemez | Erişemez |
| saglik_sorumlusu | Erişemez | Erişemez |
| guvenlik_operasyon | Erişemez | Erişemez |
| uye | Erişemez | Erişemez |
| sporcu | Erişemez | Erişemez |
| veli | Erişemez | Erişemez |
| misafir | Erişemez | Erişemez |

## Kısıtın kapsamı

- `management_only=true`, `MYK-POL-*` / `MYK-SOZ-*` kodu veya açık/geçmiş bir yenileme kaydı belgeyi yönetimle sınırlar.
- 0030 migration mevcut MYK poliçe/sözleşme kodlarını işaretler. Yenileme kaydedilince bağlı belge de işaretlenir.
- Liste, detay, revizyon ve indirme yollarında backend kontrolü vardır. Yönetim belgeleri eğitim kütüphanesinde gösterilmez.
- Belgenin sporcuya veya veliye bağlanması yönetim kısıtını aşmaz. Yenilemenin kapatılması veya kodun değiştirilmesi kısıtı kaldırmaz.
- Muhasebe yenileme tarihlerine, sorumluya, referans numarasına ve notlara erişir; asıl belge dosyasına erişemez.
- Kısıtlı dosyalar istemciye depolama URL'si verilmeden, her indirmede yeniden yetki kontrolüyle sunulur.
- Okuma için `:own` izni oluşturma/düzenleme/silme izni sağlamaz. Kişisel belgelerde veli bağlantısı aktif olmalıdır.

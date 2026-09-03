-- Preflight kontrolü: Migration 0025 öncesi çalıştırılmalı.
-- Bu betik SALT OKUNUR bir transaction içinde çalışır; hiçbir veriyi değiştirmez.
--
-- Çalıştırma:
--   psql $DATABASE_URL -f scripts/preflight_0025_check_duplicates.sql
--
-- Beklenen çıktı: "0 satır" (sonuç yoksa migration güvenle çalıştırılabilir).
-- Herhangi bir satır dönerse bu kayıtları önce temizleyin.

BEGIN TRANSACTION READ ONLY;

SELECT
    club_id,
    code,
    COUNT(*)              AS toplam_kayit,
    array_agg(id)         AS kategori_idler,
    array_agg(is_active)  AS aktif_durumlar,
    array_agg(name)       AS isimler
FROM doc_categories
GROUP BY club_id, code
HAVING COUNT(*) > 1
ORDER BY toplam_kayit DESC, club_id, code;

ROLLBACK;

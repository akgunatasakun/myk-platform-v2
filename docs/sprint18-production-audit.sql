-- Sprint 18 — P0 Production Salt-Okunur Veri Denetimi
-- HIÇBIR VERİ DEĞİŞTİRMEZ.
-- BEGIN TRANSACTION READ ONLY garantisi DB seviyesinde korunur.
--
-- Çalıştırma (Mac terminalden):
--
--   cd "/Users/akgunatasakun/Documents/Claude/Projects/Mersin Sailing Club/myk-platform-v2"
--   scp docs/sprint18-production-audit.sql myk-server:/tmp/sprint18-production-audit.sql
--   ssh myk-server
--
-- Sunucuda:
--
--   docker exec -i myk-production-db-1 sh -lc \
--     'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < /tmp/sprint18-production-audit.sql

BEGIN TRANSACTION READ ONLY;

\echo '============================================================'
\echo 'P0-1: Non-deleted Userlarda duplicate person_id'
\echo '      Beklenen: 0 satir. Herhangi bir satir migration oncesi temizlik gerektirir.'
\echo '============================================================'
SELECT person_id,
       COUNT(*)       AS hesap_sayisi,
       array_agg(id)  AS user_idler
FROM users
WHERE person_id IS NOT NULL
  AND is_deleted IS FALSE
GROUP BY person_id
HAVING COUNT(*) > 1
ORDER BY hesap_sayisi DESC;

\echo ''
\echo '============================================================'
\echo 'P0-2: Ayni kulupte duplicate e-posta (aktif + silinmis karisik)'
\echo '      Aktif satirlar varsa: migration oncesi dikkat gerekir.'
\echo '      Silinmis + aktif cakismasi restore politikasi icin bilgi amacli.'
\echo '============================================================'
SELECT club_id,
       email,
       COUNT(*) AS toplam,
       SUM(CASE WHEN is_deleted IS FALSE THEN 1 ELSE 0 END) AS aktif,
       SUM(CASE WHEN is_deleted IS TRUE  THEN 1 ELSE 0 END) AS silinmis
FROM users
GROUP BY club_id, email
HAVING COUNT(*) > 1
ORDER BY club_id, email;

\echo ''
\echo '============================================================'
\echo 'P0-3: Silinmis User e-postasıyla cakisan aktif User (restore senaryosu)'
\echo '      Mevcut (club_id, email) unique index kalacak;'
\echo '      silinmis hesabin yerini restore endpoint alacak.'
\echo '============================================================'
SELECT u_aktif.club_id,
       u_aktif.email,
       u_aktif.id          AS aktif_user_id,
       u_del.id            AS silinmis_user_id,
       u_del.created_at    AS silinmis_olusturulma
FROM users u_aktif
JOIN users u_del
  ON u_aktif.club_id = u_del.club_id
 AND u_aktif.email   = u_del.email
 AND u_aktif.id     <> u_del.id
WHERE u_aktif.is_deleted IS FALSE
  AND u_del.is_deleted   IS TRUE
ORDER BY u_aktif.club_id, u_aktif.email;

\echo ''
\echo '============================================================'
\echo 'P0-4: person_id baska kulupteki Persona bagli User (tenant sizintisi)'
\echo '      Beklenen: 0 satir. Herhangi bir satir kritik tutarsizliktir.'
\echo '============================================================'
SELECT u.id          AS user_id,
       u.club_id     AS user_club_id,
       u.person_id,
       p.club_id     AS person_club_id,
       u.email
FROM users u
JOIN persons p ON u.person_id = p.id
WHERE u.club_id     <> p.club_id
  AND u.is_deleted IS FALSE;

\echo ''
\echo '============================================================'
\echo 'P0-5: Person baglantisi olan ama Person pasif/silinmis aktif User'
\echo '      Beklenen: 0 satir.'
\echo '============================================================'
SELECT u.id              AS user_id,
       u.email,
       u.role,
       p.id              AS person_id,
       p.is_active       AS person_aktif,
       p.is_deleted      AS person_silinmis
FROM users u
JOIN persons p ON u.person_id = p.id
WHERE u.is_deleted IS FALSE
  AND u.is_active  IS TRUE
  AND (p.is_active IS FALSE OR p.is_deleted IS TRUE)
ORDER BY u.club_id;

\echo ''
\echo '============================================================'
\echo 'P0-6: Person.must_change_password=TRUE olup bagli aktif User olmayan kayitlar'
\echo '      Backfill kapsami: Migration 0019 bunlari User.must_change_password=TRUE yapar.'
\echo '============================================================'
SELECT p.id                                    AS person_id,
       p.first_name || ' ' || p.last_name      AS ad_soyad,
       p.email,
       p.club_id
FROM persons p
LEFT JOIN users u
       ON u.person_id = p.id
      AND u.is_deleted IS FALSE
WHERE p.must_change_password IS TRUE
  AND u.id         IS NULL
  AND p.is_deleted IS FALSE
ORDER BY p.club_id;

\echo ''
\echo '============================================================'
\echo 'P0-7: Her kulupte aktif kulup_yonetici sayisi'
\echo '      Beklenen: her kulupte >= 1.'
\echo '============================================================'
SELECT c.slug  AS kulup,
       c.id    AS club_id,
       COUNT(u.id) AS aktif_yonetici_sayisi
FROM clubs c
LEFT JOIN users u
       ON u.club_id   = c.id
      AND u.role      = 'kulup_yonetici'
      AND u.is_active  IS TRUE
      AND u.is_deleted IS FALSE
WHERE c.is_active IS TRUE
GROUP BY c.slug, c.id
ORDER BY aktif_yonetici_sayisi ASC, c.slug;

\echo ''
\echo '============================================================'
\echo 'P0-8: Case-insensitive duplicate e-posta (buyuk/kucuk harf farki)'
\echo '      Beklenen: 0 satir. Bulunursa migration oncesi normalize edilmeli.'
\echo '============================================================'
SELECT club_id,
       lower(email)   AS email_lower,
       COUNT(*)        AS toplam,
       array_agg(email ORDER BY email) AS varyantlar,
       array_agg(id   ORDER BY email) AS user_idler
FROM users
WHERE is_deleted IS FALSE
GROUP BY club_id, lower(email)
HAVING COUNT(*) > 1
ORDER BY club_id, email_lower;

\echo ''
\echo '============================================================'
\echo 'P0-9: User.role sporcu/antrenor ile bagli PersonRole uyumsuzlugu'
\echo '      Beklenen: 0 satir. K1 kurali: sporcu/antrenor User -> PersonRole eslemesi zorunlu.'
\echo '============================================================'
SELECT u.id          AS user_id,
       u.email,
       u.role         AS user_role,
       u.club_id,
       pr.role_code   AS person_role_code
FROM users u
LEFT JOIN persons p
       ON u.person_id = p.id
      AND p.is_deleted IS FALSE
LEFT JOIN person_roles pr
       ON pr.person_id = p.id
      AND pr.role_code  = u.role
WHERE u.role IN ('sporcu', 'antrenor')
  AND u.is_deleted IS FALSE
  AND u.is_active  IS TRUE
  AND pr.role_code IS NULL   -- PersonRole eslesmiyor
ORDER BY u.club_id, u.role;

ROLLBACK;

\echo ''
\echo '============================================================'
\echo 'P0 denetimi tamamlandi. Sonuclari Claude ile paylasin.'
\echo '============================================================'

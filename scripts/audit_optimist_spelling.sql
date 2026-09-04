\echo 'Optmist/benzeri yazım hataları — salt okunur production denetimi'
BEGIN TRANSACTION READ ONLY;

SELECT 'training_courses.class_name' AS kaynak, id, club_id, class_name AS deger
FROM training_courses
WHERE class_name ~* 'optm[ıi]st'
UNION ALL
SELECT 'athlete_profiles.class_name', id, club_id, class_name
FROM athlete_profiles
WHERE class_name ~* 'optm[ıi]st'
UNION ALL
SELECT 'equipment.name', id, club_id, name
FROM equipment
WHERE name ~* 'optm[ıi]st'
UNION ALL
SELECT 'equipment.model', id, club_id, model
FROM equipment
WHERE model ~* 'optm[ıi]st'
ORDER BY kaynak, club_id, id;

ROLLBACK;

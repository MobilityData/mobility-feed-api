DROP VIEW IF EXISTS location_with_translations;
DROP VIEW IF EXISTS location_with_translations_en;
CREATE VIEW location_with_translations_en AS
SELECT
    l.id AS location_id,
    l.country_code,
    l.country,
    l.subdivision_name,
    l.municipality,
    country_translation.value AS country_translation,
    subdivision_name_translation.value AS subdivision_name_translation,
    municipality_translation.value AS municipality_translation
FROM
    location l
LEFT JOIN
    translation AS country_translation
    ON l.country = country_translation.key
    AND country_translation.type = 'country'
    AND country_translation.language_code = 'en'
LEFT JOIN
    translation AS subdivision_name_translation
    ON l.subdivision_name = subdivision_name_translation.key
    AND subdivision_name_translation.type = 'subdivision_name'
    AND subdivision_name_translation.language_code = 'en'
LEFT JOIN
    translation AS municipality_translation
    ON l.municipality = municipality_translation.key
    AND municipality_translation.type = 'municipality'
    AND municipality_translation.language_code = 'en';
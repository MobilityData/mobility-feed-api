SELECT DISTINCT ON (f.stable_id)
	f.stable_id,  -- Only stable_id and urls.latest are necessary in the resulting list.
                  -- theothers are for informational purposes
    f.provider,
    l.country_code,
   	l.subdivision_name,
    l.municipality,
	CONCAT('https://files.mobilitydatabase.org/', f.stable_id, '/latest.zip') AS "urls.latest"
FROM feed AS f
         JOIN locationfeed AS lf
              ON lf.feed_id = f.id
         JOIN location AS l
              ON l.id = lf.location_id
WHERE f.data_type = 'gtfs'
  AND f.stable_id LIKE 'mdb-%'
  AND f.status <> 'deprecated'
  AND f.operational_status = 'published'
  AND f.stable_id NOT IN ('mdb-784', 'mdb-1081', 'mdb-1078') -- Exclude specific feeds because they take too long
  AND (
    l.country_code <> 'US'
        OR l.country_code IS NULL
        OR f.provider ILIKE 'Chicago Transit Authority%'
        OR l.subdivision_name ILIKE 'California%'
        OR l.subdivision_name ILIKE 'New York%'
        OR f.provider ILIKE 'Miami-Dade Transit%'
)
GROUP BY f.stable_id,
         f.provider,
         l.country_code,
         l.subdivision_name,
         l.municipality
ORDER BY f.stable_id;

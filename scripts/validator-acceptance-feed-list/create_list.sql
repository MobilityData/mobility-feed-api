SELECT DISTINCT ON (f.stable_id)
	f.stable_id,  -- Only stable_id and urls.latest are necessary in the resulting list.
                  -- the others are for informational purposes
    f.provider,
    l.country_code,
   	l.subdivision_name,
    l.municipality,
	CONCAT('https://files.mobilitydatabase.org/', f.stable_id, '/latest.zip') AS "urls.latest"
FROM feed AS f
JOIN gtfsfeed AS gf ON gf.id = f.id
JOIN locationfeed AS lf ON lf.feed_id = f.id
JOIN location AS l ON l.id = lf.location_id
WHERE f.data_type = 'gtfs'
  AND f.stable_id LIKE 'mdb-%'
  AND f.status <> 'deprecated'
  AND f.operational_status = 'published'
  AND f.stable_id NOT IN ( -- Exclude specific feeds because they take too long
    'mdb-784',
    'mdb-1081',
    'mdb-1078'
  )
  AND gf.latest_dataset_id IS NOT NULL
  AND (
    l.country_code <> 'US'
    OR l.country_code IS NULL
    OR f.provider ILIKE 'Chicago Transit Authority%'
    OR l.subdivision_name ILIKE 'California%'
    OR l.subdivision_name ILIKE 'New York%'
    OR f.provider ILIKE 'Miami-Dade Transit%'
    OR f.stable_id IN (   -- Cover specific notices
        'mdb-2164',  -- To cover invalid_geometry notice
        'mdb-2447',  -- To cover invalid_pickup_drop_off_window and missing_pickup_drop_off_booking_rule_id notices
        'mdb-2446',  -- To cover missing_pickup_or_drop_off_window notice
        'mdb-2165',  -- To cover missing_prior_day_booking_field_value (validator 6 only) and missing_prior_notice_last_time notices
        'mdb-2831',  -- To cover overlapping_zone_and_pickup_drop_off_window notice
        'mdb-2882'   -- To cover forbidden_shape_dist_traveled notice
    )
)
ORDER BY f.stable_id;

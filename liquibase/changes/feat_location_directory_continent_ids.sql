-- Stable location ids of the continents of the feed location directory. Continents are rows of the
-- geopolygonlocationsearch view next to the OpenStreetMap areas, so their ids are negative to never collide with an
-- OSM id. They are part of the public API (`location_id` of /v1/locations and /v1/search): never change them.
ALTER TABLE continent ADD COLUMN IF NOT EXISTS location_id INTEGER;

UPDATE continent SET location_id = CASE code
    WHEN 'AF' THEN -1
    WHEN 'AN' THEN -2
    WHEN 'AS' THEN -3
    WHEN 'EU' THEN -4
    WHEN 'NA' THEN -5
    WHEN 'OC' THEN -6
    WHEN 'SA' THEN -7
END;

ALTER TABLE continent ALTER COLUMN location_id SET NOT NULL;

ALTER TABLE continent ADD CONSTRAINT continent_location_id_key UNIQUE (location_id);

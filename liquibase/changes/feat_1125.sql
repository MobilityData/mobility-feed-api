-- Update gbfsendpoint table to set is_feature = false for specific endpoints
UPDATE gbfsendpoint
SET is_feature = false
WHERE name IN ('station_information', 'system_hours', 'system_calendar')
AND is_feature = true;
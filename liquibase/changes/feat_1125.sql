-- Update gbfsendpoint table to set is_feature = false for specific endpoints
UPDATE gbfsendpoint
SET is_feature = CASE
    WHEN name IN (
        'manifest',
        'gbfs_versions',
        'vehicle_types',
        'station_status',
        'vehicle_status',
        'system_regions',
        'system_pricing_plans',
        'system_alerts',
        'geofencing_zones'
    ) THEN true
    ELSE false
END;
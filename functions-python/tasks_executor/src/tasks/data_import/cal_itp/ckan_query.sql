SELECT
    provider_gtfs_data.service_source_record_id,
    provider_gtfs_data.service_name,
    provider_gtfs_data.organization_source_record_id,
    provider_gtfs_data.organization_name,
    organizations.caltrans_district_name,
    provider_gtfs_data.schedule_source_record_id,
    provider_gtfs_data.schedule_gtfs_dataset_name,
    schedule_dataset.url AS schedule_dataset_url,
    provider_gtfs_data.service_alerts_source_record_id,
    provider_gtfs_data.service_alerts_gtfs_dataset_name,
    service_alerts_dataset.url AS service_alerts_dataset_url,
    provider_gtfs_data.trip_updates_source_record_id,
    provider_gtfs_data.trip_updates_gtfs_dataset_name,
    trip_updates_dataset.url AS trip_updates_dataset_url,
    provider_gtfs_data.vehicle_positions_source_record_id,
    provider_gtfs_data.vehicle_positions_gtfs_dataset_name,
    vehicle_positions_dataset.url AS vehicle_positions_dataset_url,
    provider_gtfs_data.regional_feed_type,
    provider_gtfs_data.gtfs_service_data_customer_facing
FROM "{services}" services
INNER JOIN "{provider_gtfs_data}" provider_gtfs_data
    ON services.source_record_id = provider_gtfs_data.service_source_record_id
INNER JOIN "{organizations}" organizations
    ON provider_gtfs_data.organization_source_record_id = organizations.source_record_id
LEFT JOIN "{gtfs_dataset}" schedule_dataset
    ON provider_gtfs_data.schedule_source_record_id = schedule_dataset.source_record_id
LEFT JOIN "{gtfs_dataset}" service_alerts_dataset
    ON provider_gtfs_data.service_alerts_source_record_id = service_alerts_dataset.source_record_id
LEFT JOIN "{gtfs_dataset}" trip_updates_dataset
    ON provider_gtfs_data.trip_updates_source_record_id = trip_updates_dataset.source_record_id
LEFT JOIN "{gtfs_dataset}" vehicle_positions_dataset
    ON provider_gtfs_data.vehicle_positions_source_record_id = vehicle_positions_dataset.source_record_id
WHERE services.is_public = 'Yes'
AND (
    provider_gtfs_data.schedule_source_record_id IS NOT NULL OR
    provider_gtfs_data.service_alerts_source_record_id IS NOT NULL OR
    provider_gtfs_data.trip_updates_source_record_id IS NOT NULL OR
    provider_gtfs_data.vehicle_positions_source_record_id IS NOT NULL
)

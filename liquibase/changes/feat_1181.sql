UPDATE gbfsendpoint
SET
  name = 'free_bike_status',
  is_feature = TRUE
WHERE
  name = 'vehicle_status'
;
ALTER TABLE gtfsdataset 
ADD COLUMN service_date_range_timezone TIMESTAMP WITH TIME ZONE 
DEFAULT date_trunc('day', now()) AT TIME ZONE 'UTC';

-- Adding alternative names to the geolocation table
ALTER TABLE geopolygon
ADD COLUMN IF NOT EXISTS alt_name VARCHAR(255);

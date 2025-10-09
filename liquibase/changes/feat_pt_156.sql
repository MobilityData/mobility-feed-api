-- Add the new columns to gbfsfeed (if not already added)
-- No foreign keys to versions as versions are not kept between updates
ALTER TABLE gbfsfeed
  ADD COLUMN IF NOT EXISTS bounding_box geometry(Polygon, 4326);
ALTER TABLE gbfsfeed
  ADD COLUMN IF NOT EXISTS bounding_box_generated_at TIMESTAMP DEFAULT NULL;

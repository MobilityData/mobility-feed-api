-- Who last wrote a per-feed config override through the Operations API. Null for rows
-- written by migrations or by code (e.g. the Parquet builder recording a size).
ALTER TABLE config_value_feed ADD COLUMN IF NOT EXISTS updated_by text;

-- Create indexes to enhance SQL queries running like commands against license id and name
-- This changeset is executed after enabling the pg_trgm extension in a different transaction

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_license_lower_name_trgm
  ON license USING gin (lower(name) gin_trgm_ops);
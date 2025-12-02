-- Create indexes to enhance SQL queries running like commands againts license id and name

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_license_lower_name
  ON license ((lower(name)));

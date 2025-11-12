-- Add the 'license_id' and license_notes columns to the 'feed' table if it doesn't exist
ALTER TABLE feed ADD COLUMN IF NOT EXISTS license_id TEXT;
ALTER TABLE feed ADD COLUMN IF NOT EXISTS license_notes TEXT;

-- Add a foreign key constraint to reference the 'licenses' table
ALTER TABLE feed
  ADD CONSTRAINT fk_feed_license
  FOREIGN KEY (license_id) REFERENCES license (id)
  ON DELETE SET NULL
  NOT VALID;

ALTER TABLE feed VALIDATE CONSTRAINT fk_feed_license;

-- Audit table for feed license matching changes
CREATE TABLE IF NOT EXISTS feed_license_change (
    id BIGSERIAL PRIMARY KEY,
    feed_id             VARCHAR(255) NOT NULL,
    changed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    feed_license_url    TEXT,
    matched_license_id  TEXT,
    confidence          DOUBLE PRECISION,
    match_type          TEXT,
    matched_name        TEXT,
    matched_catalog_url TEXT,
    matched_source      TEXT,
    notes               TEXT,
    regional_id         TEXT,
    CONSTRAINT feed_license_change_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES Feed(id) ON DELETE CASCADE ON UPDATE NO ACTION,
    CONSTRAINT feed_license_change_matched_license_id_fkey FOREIGN KEY (matched_license_id) REFERENCES License(id) ON DELETE SET NULL ON UPDATE NO ACTION
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_feed_license_id
  ON feed (license_id);

CREATE INDEX IF NOT EXISTS ix_flc_feed_changed_at
  ON feed_license_change (feed_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS ix_flc_matched_license
  ON feed_license_change (matched_license_id);

CREATE INDEX IF NOT EXISTS ix_flc_match_type
  ON feed_license_change (match_type);

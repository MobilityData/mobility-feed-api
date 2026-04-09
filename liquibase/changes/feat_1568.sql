-- Add verified column to feed_license_change to track human review status.
-- Auto-assigned licenses start as unverified (false = needs review);
-- manually confirmed or high-confidence assignments are marked true.
ALTER TABLE feed_license_change ADD COLUMN IF NOT EXISTS verified BOOLEAN NOT NULL DEFAULT false;

-- Backfill all pre-existing rows as verified — prior assignments are considered trusted.
UPDATE feed_license_change SET verified = true;

-- Index for efficient filtering of unverified assignments.
CREATE INDEX IF NOT EXISTS ix_flc_verified ON feed_license_change (verified);

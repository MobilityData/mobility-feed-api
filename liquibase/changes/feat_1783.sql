-- Issue #1783: Seal of Reliability algorithm (spec in #1761). Adjusts the tables added by
-- feat_1760.sql. Nothing reads them yet, so this renames in place.

-- The two status booleans become positive: TRUE now means the criterion passed.
ALTER TABLE SealCriterion RENAME COLUMN raw_failing TO observed_pass;
ALTER TABLE SealCriterion RENAME COLUMN grace_failing TO confirmed_pass;
UPDATE SealCriterion SET observed_pass = NOT observed_pass WHERE observed_pass IS NOT NULL;
UPDATE SealCriterion SET confirmed_pass = NOT confirmed_pass WHERE confirmed_pass IS NOT NULL;

-- The timestamps stay negative: they record events that really are failures.
ALTER TABLE SealCriterion RENAME COLUMN first_raw_failure_at TO first_observed_failure_at;
ALTER TABLE SealCriterion RENAME COLUMN last_raw_failure_at TO last_observed_failure_at;
ALTER TABLE SealCriterion RENAME COLUMN last_grace_failure_at TO last_confirmed_failure_at;

ALTER TABLE SealCriterion ADD COLUMN IF NOT EXISTS probation_start TIMESTAMPTZ;

COMMENT ON COLUMN SealCriterion.observed_pass IS
    'The criterion''s own check on this day, with no debouncing. NULL = never evaluated.';
COMMENT ON COLUMN SealCriterion.confirmed_pass IS
    'The debounced status, FALSE once an observed failure outlasts the grace period. '
    'NULL = never evaluated.';
COMMENT ON COLUMN SealCriterion.probation_start IS
    'Start of the 180 days with no observed failure a criterion serves after recovering '
    'from a confirmed failure. NULL = not on probation.';

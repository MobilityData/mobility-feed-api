-- Issue #1783: revised Seal of Reliability algorithm (spec in #1761).
-- Adjusts the tables added by feat_1760.sql. Nothing reads them yet, so this is safe to
-- apply as a rename rather than an additive migration.

-- 1. The two status booleans flip to positive polarity and are renamed.
--    `has_seal` is already positive and every criterion check is written positively
--    (`success = TRUE`, `total_error = 0`), so negative status columns forced an inversion
--    at both ends. `raw` also described how a value was produced rather than what it means
--    and had no opposite pole, which left `grace` on a different axis; observed ->
--    confirmed is one axis, and the grace period is the distance along it.
ALTER TABLE SealCriterion RENAME COLUMN raw_failing TO observed_pass;
ALTER TABLE SealCriterion RENAME COLUMN grace_failing TO confirmed_pass;

--    The failure timestamps keep their negative sense on purpose: they record events that
--    really are failures, and the grace period is measured from the start of a bad streak.
--    Booleans describe state, timestamps record events.
ALTER TABLE SealCriterion RENAME COLUMN first_raw_failure_at TO first_observed_failure_at;
ALTER TABLE SealCriterion RENAME COLUMN last_raw_failure_at TO last_observed_failure_at;
ALTER TABLE SealCriterion RENAME COLUMN last_grace_failure_at TO last_confirmed_failure_at;

--    These are inversions, not just renames: TRUE meant failing and now means passing.
--    NULL keeps its meaning of "not yet evaluated" and must stay NULL.
UPDATE SealCriterion SET observed_pass = NOT observed_pass WHERE observed_pass IS NOT NULL;
UPDATE SealCriterion SET confirmed_pass = NOT confirmed_pass WHERE confirmed_pass IS NOT NULL;

COMMENT ON COLUMN SealCriterion.observed_pass IS
    'The criterion''s own check on this day, with no debouncing. NULL = never evaluated.';
COMMENT ON COLUMN SealCriterion.confirmed_pass IS
    'The debounced status. FALSE once an observed failure outlasts the grace period, or '
    'immediately for a criterion with no grace period. NULL = never evaluated.';

-- 2. probation_start replaces the reliability window, which used to be an implicit lookback
--    over last_grace_failure_at. Probation is a penalty rather than an entry requirement: a
--    criterion is put on it by a recovery, never by a first evaluation, so a feed that has
--    never had a confirmed failure can hold the seal from its first evaluation.
ALTER TABLE SealCriterion ADD COLUMN IF NOT EXISTS probation_start TIMESTAMPTZ;

COMMENT ON COLUMN SealCriterion.probation_start IS
    'Start of the 180-day stretch with no observed failure that this criterion must '
    'complete before it can contribute to the seal again. Started by a recovery from a '
    'confirmed failure, or by a recovery from an observed failure while already on '
    'probation. NULL = not on probation: nothing has gone wrong yet, probation was served '
    'out, or the criterion has no probation at all.';

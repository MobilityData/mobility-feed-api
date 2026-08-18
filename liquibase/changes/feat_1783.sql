-- Issue #1783: Seal of Reliability status enum and per-criterion tracking columns, on the
-- #1760 tables.

CREATE TYPE seal_criterion_status AS ENUM (
    'pass',
    'fail',
    'unknown',
    'never_evaluated',
    'not_applicable'
);

ALTER TABLE SealCriterion
    DROP COLUMN IF EXISTS raw_failing,
    DROP COLUMN IF EXISTS grace_failing,
    ADD COLUMN observed_status seal_criterion_status NOT NULL DEFAULT 'never_evaluated',
    ADD COLUMN confirmed_status seal_criterion_status NOT NULL DEFAULT 'never_evaluated';

ALTER TABLE SealCriterion RENAME COLUMN first_raw_failure_at TO first_observed_failure_at;
ALTER TABLE SealCriterion RENAME COLUMN last_raw_failure_at TO last_observed_failure_at;
ALTER TABLE SealCriterion RENAME COLUMN last_grace_failure_at TO last_confirmed_failure_at;

ALTER TABLE SealCriterion ADD COLUMN IF NOT EXISTS probation_start TIMESTAMPTZ;
ALTER TABLE SealCriterion ADD COLUMN IF NOT EXISTS last_verdict_at TIMESTAMPTZ;

COMMENT ON COLUMN SealCriterion.observed_status IS
    'The check on this day, no debouncing. pass/fail are verdicts; unknown = inputs missing; '
    'not_applicable = excluded for this feed; never_evaluated = never had a verdict.';
COMMENT ON COLUMN SealCriterion.confirmed_status IS
    'Debounced status. Never unknown; not_applicable withdraws the criterion from has_seal.';
COMMENT ON COLUMN SealCriterion.evaluated_at IS 'Last attempt, any outcome. Not read by the algorithm.';
COMMENT ON COLUMN SealCriterion.last_verdict_at IS 'Last pass or fail. NULL = never evaluated.';
COMMENT ON COLUMN SealCriterion.probation_start IS
    'Start of the 180-day probation. NULL = not on probation. May be a future date mid-streak.';

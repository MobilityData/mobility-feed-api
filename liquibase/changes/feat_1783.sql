-- Issue #1783: Seal of Reliability schema, reworked around probation and a positive
-- per-criterion status enum.
--
-- This changeset fully SUPERSEDES #1760: it drops everything #1760 created and rebuilds
-- the seal tables from scratch in their final shape, so the authoritative definition of
-- the whole seal schema lives here in one place. #1760 remains in the changelog (it was
-- already applied to earlier environments and must not be edited), but at runtime its
-- objects are torn down and recreated below.
--
-- At this point there is no data in the seal tables because it has not been deployed to prod,
-- so just deleting them loses nothing.

-- Teardown of the #1760 objects (tables first, then the enum types they used).
DROP TABLE IF EXISTS SealCriterion CASCADE;
DROP TABLE IF EXISTS FeedReliabilitySeal CASCADE;
DROP TYPE  IF EXISTS seal_criterion_status;
DROP TYPE  IF EXISTS seal_criterion_name;

-- The set of criteria that make up the seal.
CREATE TYPE seal_criterion_name AS ENUM (
    'official',
    'stable',
    'available',
    'compliant',
    'fresh_coverage',
    'fresh_continuous'
);

-- Per-criterion status. pass/fail are verdicts; unknown = inputs missing;
-- not_applicable = excluded for this feed; never_evaluated = never had a verdict.
CREATE TYPE seal_criterion_status AS ENUM (
    'pass',
    'fail',
    'unknown',
    'never_evaluated',
    'not_applicable'
);

-- One row per feed; owns the overall seal outcome.
-- A surrogate id keeps feed_id a plain UNIQUE foreign key rather than the primary key: the
-- PK-is-also-FK shape reads as joined-table inheritance to sqlacodegen, which would make the
-- model a subclass of Feed. UNIQUE still enforces one row per feed.
CREATE TABLE feed_reliability_seal (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_id        VARCHAR(255) NOT NULL UNIQUE REFERENCES Feed(id) ON DELETE CASCADE,

    has_seal       BOOLEAN NOT NULL DEFAULT FALSE,
    seal_earned_at TIMESTAMPTZ,
    seal_lost_at   TIMESTAMPTZ,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per feed per criterion; owns all per-criterion state.
CREATE TABLE seal_criterion (
    feed_id                    VARCHAR(255) NOT NULL REFERENCES Feed(id) ON DELETE CASCADE,
    criterion                  seal_criterion_name NOT NULL,

    -- Status
    observed_status            seal_criterion_status NOT NULL DEFAULT 'never_evaluated',
    confirmed_status           seal_criterion_status NOT NULL DEFAULT 'never_evaluated',

    -- Evaluation tracking
    evaluated_at               TIMESTAMPTZ,
    last_verdict_at            TIMESTAMPTZ,

    -- Failure tracking
    first_observed_failure_at  TIMESTAMPTZ,
    last_observed_failure_at   TIMESTAMPTZ,
    last_confirmed_failure_at  TIMESTAMPTZ,

    -- Probation
    probation_start            TIMESTAMPTZ,

    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (feed_id, criterion)
);

COMMENT ON COLUMN seal_criterion.observed_status IS
    'The check on this day, no debouncing. pass/fail are verdicts; unknown = inputs missing; '
    'not_applicable = excluded for this feed; never_evaluated = never had a verdict.';
COMMENT ON COLUMN seal_criterion.confirmed_status IS
    'Debounced status. Never unknown; not_applicable withdraws the criterion from has_seal.';
COMMENT ON COLUMN seal_criterion.evaluated_at IS 'Last attempt, any outcome. Not read by the algorithm.';
COMMENT ON COLUMN seal_criterion.last_verdict_at IS 'Last pass or fail. NULL = never evaluated.';
COMMENT ON COLUMN seal_criterion.probation_start IS
    'Start of the 180-day probation. NULL = not on probation. May be a future date mid-streak.';

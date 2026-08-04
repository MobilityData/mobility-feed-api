-- Add Seal of Reliability tables (issue #1760).
-- These tables denormalize data already present in gtfs_feed_availability_check,
-- validationreport, and gtfsdataset. Following the existing pattern (e.g.
-- gtfsfeed.latest_dataset_id): raw tables remain the append-only source of truth,
-- while the seal tables are a nightly-computed cache that lets the API answer
-- "does this feed have the seal?" in a single row lookup with no joins.
-- See #1761 for the usage of these tables.

-- One row per feed; owns the overall seal outcome.
CREATE TABLE IF NOT EXISTS feed_reliability_seal (
    feed_id        VARCHAR(255) PRIMARY KEY,

    has_seal       BOOLEAN NOT NULL DEFAULT FALSE,
    seal_earned_at TIMESTAMPTZ,
    seal_lost_at   TIMESTAMPTZ,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT feed_reliability_seal_feed_id_fkey
        FOREIGN KEY (feed_id)
        REFERENCES gtfsfeed(id)
        ON DELETE CASCADE
);

CREATE TYPE seal_criterion_name AS ENUM (
    'official',
    'stable',
    'available',
    'compliant',
    'fresh_coverage',
    'fresh_continuous'
);

-- One row per feed per criterion; owns all per-criterion state.
-- raw_* columns reflect the instantaneous state at the last evaluation, with no grace applied.
-- grace_* columns reflect the debounced state: a failure is only confirmed after its grace period expires.
-- The seal logic is driven exclusively by grace_* columns; raw_* columns are for monitoring and audit.
CREATE TABLE IF NOT EXISTS seal_criterion (
    feed_id                        VARCHAR(255) NOT NULL,
    criterion                      seal_criterion_name NOT NULL,

    -- Current state
    raw_failing                    BOOLEAN,      -- NULL = not yet evaluated; TRUE = failing at last check, no grace applied
    grace_failing                  BOOLEAN,      -- NULL = not yet evaluated; TRUE = failure has persisted beyond the grace period

    -- Evaluation tracking
    evaluated_at                   TIMESTAMPTZ,

    -- Failure tracking
    first_raw_failure_at           TIMESTAMPTZ,  -- start of current raw failure streak; cleared on recovery
    last_raw_failure_at            TIMESTAMPTZ,  -- end of last raw failure streak; never cleared
    last_grace_failure_at          TIMESTAMPTZ,  -- end of the grace period failure; never cleared

    created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (feed_id, criterion),

    CONSTRAINT seal_criterion_feed_id_fkey
        FOREIGN KEY (feed_id)
        REFERENCES gtfsfeed(id)
        ON DELETE CASCADE
);

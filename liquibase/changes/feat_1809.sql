-- Issue #1809: keep the state of each seal criterion on every day it is evaluated, so past
-- values survive and a correction can resume from the day before the change instead of
-- cold-starting the window. seal_criterion is unchanged and still holds the current state.
--
-- A DATE key rather than a timestamp, so re-running or replaying a day overwrites it. No
-- cadence is assumed: gaps are normal, and a reader takes the latest row on or before the
-- day it asks about.

CREATE TABLE seal_criterion_snapshot (
    feed_id                    VARCHAR(255) NOT NULL REFERENCES Feed(id) ON DELETE CASCADE,
    criterion                  seal_criterion_name NOT NULL,
    snapshot_date              DATE NOT NULL,

    observed_status            seal_criterion_status NOT NULL,
    confirmed_status           seal_criterion_status NOT NULL,

    last_verdict_at            TIMESTAMPTZ,
    first_observed_failure_at  TIMESTAMPTZ,
    probation_start            TIMESTAMPTZ,
    last_observed_failure_at   TIMESTAMPTZ,
    last_confirmed_failure_at  TIMESTAMPTZ,

    PRIMARY KEY (feed_id, criterion, snapshot_date)
);

-- For whole-catalogue-on-a-day queries and retention deletes; the primary key already
-- covers a single feed's snapshots.
CREATE INDEX idx_seal_criterion_snapshot_date
    ON seal_criterion_snapshot (snapshot_date);

COMMENT ON TABLE seal_criterion_snapshot IS
    'State of each seal criterion per feed and evaluated day. seal_criterion holds the '
    'current state; this holds the record.';

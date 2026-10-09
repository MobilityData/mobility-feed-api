-- Append-only history of individual task attempts.
--
-- task_execution_log holds one row per (task_name, entity_id, run_id) and rewrites it in
-- place: try_acquire nulls error_message and completed_at and resets triggered_at, and
-- metadata is overwritten whole by every heartbeat. That row answers "where does this
-- entity stand now" and cannot answer "what has happened to it", which is what sizing
-- decisions and a retry cap both need.
--
-- One row per attempt, never updated. Deliberately not keyed to task_execution_log: a row
-- there may be rewritten or, for a run that is cleaned up, removed, and the history should
-- outlive it.
CREATE TABLE task_execution_attempt (
    id               BIGSERIAL PRIMARY KEY,
    task_name        VARCHAR     NOT NULL,
    entity_id        VARCHAR,
    run_id           VARCHAR     NOT NULL,
    -- 1-based, counted since the entity last succeeded.
    attempt          INTEGER     NOT NULL,
    -- Which worker ran it, and why that one was chosen. `variant` alone says what ran;
    -- the other three are what make a move up or down legible rather than inferred from
    -- comparing neighbouring rows.
    variant          VARCHAR,
    variant_basis    VARCHAR,
    floor_at_attempt VARCHAR,
    escalated_to     VARCHAR,
    status           VARCHAR     NOT NULL,
    -- Null on success. Resource kinds are the ones an escalation may act on.
    failure_kind     VARCHAR,
    -- The exception class, separately from its message: str(MemoryError()) is the empty
    -- string, so the failure the largest worker exists for cannot be recognised from the
    -- message alone.
    error_type       VARCHAR,
    error_message    TEXT,
    started_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms      BIGINT,
    peak_rss_bytes   BIGINT,
    -- Address space, which is what RLIMIT_AS caps. Sizing from RSS under-provisions by
    -- roughly half.
    peak_vms_bytes   BIGINT,
    metadata         JSONB
);

-- "What has happened to this entity", for the retry cap and the per-feed history.
CREATE INDEX idx_task_execution_attempt_entity
    ON task_execution_attempt (task_name, entity_id, run_id, finished_at DESC);

-- "How is this task doing lately", for the stats report.
CREATE INDEX idx_task_execution_attempt_task_time
    ON task_execution_attempt (task_name, finished_at DESC);

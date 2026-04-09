-- Generic task run tracking table.
-- One record per orchestration run (process level).
-- Mirrors the BatchExecution concept from DatasetTraceService (Datastore),
-- allowing future migration of batch_process_dataset, batch_datasets, gbfs_validator.
CREATE TABLE IF NOT EXISTS task_run (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name    VARCHAR NOT NULL,
    run_id       VARCHAR NOT NULL,
    status       VARCHAR NOT NULL,
    total_count  INTEGER,
    params       JSONB,
    created_at   TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    UNIQUE (task_name, run_id)
);

-- Generic task execution log table.
-- One record per entity/workflow execution within a run.
-- entity_id is nullable for tasks that do not operate on a specific entity.
-- Mirrors the DatasetTrace concept from DatasetTraceService (Datastore).
CREATE TABLE IF NOT EXISTS task_execution_log (
    id               SERIAL PRIMARY KEY,
    task_run_id      UUID REFERENCES task_run(id),
    task_name        VARCHAR NOT NULL,
    entity_id        VARCHAR,
    run_id           VARCHAR NOT NULL,
    status           VARCHAR NOT NULL,
    execution_ref    VARCHAR,
    error_message    TEXT,
    metadata         JSONB,
    triggered_at     TIMESTAMP DEFAULT NOW(),
    completed_at     TIMESTAMP,
    UNIQUE (task_name, entity_id, run_id)
);

CREATE INDEX IF NOT EXISTS ix_task_run_task_name_run_id ON task_run (task_name, run_id);
CREATE INDEX IF NOT EXISTS ix_task_execution_log_task_run_id ON task_execution_log (task_run_id);
CREATE INDEX IF NOT EXISTS ix_task_execution_log_task_name_entity_run ON task_execution_log (task_name, entity_id, run_id);
CREATE INDEX IF NOT EXISTS ix_task_execution_log_status ON task_execution_log (status);

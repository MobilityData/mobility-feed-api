-- liquibase formatted sql

-- changeset MobilityData:feat_1900
-- comment: Add user_dataset, user_task and user_task_dataset: the datasets users upload and the tasks that process them (issue #1900)

-- Datasets and tasks have no expiry column: they expire a configured number of days after
-- created_at, so changing the period applies to every row.

-- A file a user uploaded.
CREATE TABLE user_dataset (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id    TEXT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name       TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
    size_bytes BIGINT CHECK (size_bytes >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_dataset_user_created ON user_dataset (user_id, created_at DESC);

-- A unit of work a user started on one or more datasets, such as the Garage conversion. Its
-- execution state (status, progress, error) is in the feeds database's task_execution_log, with
-- task_name = kind and entity_id = id.
CREATE TABLE user_task (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id    TEXT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('garage')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_task_user ON user_task (user_id);

-- The datasets a task works on. A dataset can be used by several tasks. A dataset still used by a
-- task cannot be deleted: delete its tasks first. The check is deferred to commit so that deleting
-- a user, which cascades to both tables in no guaranteed order, still works.
CREATE TABLE user_task_dataset (
    task_id    TEXT NOT NULL REFERENCES user_task(id) ON DELETE CASCADE,
    dataset_id TEXT NOT NULL REFERENCES user_dataset(id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    PRIMARY KEY (task_id, dataset_id)
);
CREATE INDEX idx_user_task_dataset_dataset ON user_task_dataset (dataset_id);

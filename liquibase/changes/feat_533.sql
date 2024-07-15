-- Adding created_at column to Feed table with default value and not null constraint
ALTER TABLE Feed ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT '2024-02-08 00:00:00.000000';
-- Issue #1684: Add migrated_at to app_user
-- Tracks whether a user row was created by the migrate_firebase_users task.
-- NULL means the row was provisioned on-demand by the API (GET /v1/users/me),
-- not yet touched by the migration task.
ALTER TABLE app_user
    ADD COLUMN IF NOT EXISTS migrated_at TIMESTAMPTZ;

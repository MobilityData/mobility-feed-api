-- liquibase formatted sql

-- changeset MobilityData:feat_1694_feature_flag
-- comment: Add feature_flag and user_feature_flag tables for user-scoped feature flags (issue #1694)

CREATE TABLE feature_flag (
    id           TEXT PRIMARY KEY,    -- human-readable slug, e.g. 'beta_editor'
    name         TEXT,                -- optional display label
    description  TEXT,
    value_type   TEXT NOT NULL DEFAULT 'string'
                     CHECK (value_type IN ('boolean','string','numeric','array','json')),
    disabled     BOOLEAN NOT NULL DEFAULT false,
    default_value JSONB NOT NULL DEFAULT 'string',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_feature_flag (
    user_id         TEXT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    feature_flag_id TEXT NOT NULL REFERENCES feature_flag(id) ON DELETE CASCADE,
    value           JSONB,            -- NULL = no override, use default_value from feature_flag
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, feature_flag_id)
);

-- fan-out index: "which users have this flag?"
CREATE INDEX ON user_feature_flag (feature_flag_id);

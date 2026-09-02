-- liquibase formatted sql

-- changeset MobilityData:feat_early_access_programs
-- comment: Add early access program tables (bulk CSV-driven feature-flag grants; product-tasks#213)

CREATE TABLE early_access_program (
    id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name                  TEXT NOT NULL,
    description           TEXT,
    starts_at             TIMESTAMPTZ,
    ends_at               TIMESTAMPTZ,
    disabled              BOOLEAN NOT NULL DEFAULT false,
    invite_retention_days INTEGER NOT NULL DEFAULT 90 CHECK (invite_retention_days > 0),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by            TEXT,
    CONSTRAINT ck_early_access_window
        CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);

CREATE TABLE early_access_program_feature_flag (
    program_id      TEXT NOT NULL REFERENCES early_access_program(id) ON DELETE CASCADE,
    feature_flag_id TEXT NOT NULL REFERENCES feature_flag(id) ON DELETE CASCADE,
    -- Defaults to true because feature_flag_enabled falls back to default_value on NULL,
    -- and isSealFilterEnabled defaults to false, so granting NULL would grant nothing.
    value           JSONB NOT NULL DEFAULT 'true'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (program_id, feature_flag_id)
);
CREATE INDEX idx_eapff_feature_flag_id ON early_access_program_feature_flag (feature_flag_id);

CREATE TABLE early_access_enrollment (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    program_id  TEXT NOT NULL REFERENCES early_access_program(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source      TEXT NOT NULL DEFAULT 'invited_email'
                    CHECK (source IN ('invited_email','operations')),
    CONSTRAINT uq_early_access_enrollment UNIQUE (program_id, user_id)
);
CREATE INDEX idx_early_access_enrollment_user_id ON early_access_enrollment (user_id);
CREATE INDEX idx_early_access_enrollment_program ON early_access_enrollment (program_id, enrolled_at DESC);

-- A row exists ONLY while the invite is unclaimed. Claiming deletes it; the enrollment
-- row with source='invited_email' is the durable audit. Driven by the retention
-- requirement: we must not hold the email of someone who never registered.
CREATE TABLE early_access_invited_email (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    program_id TEXT NOT NULL REFERENCES early_access_program(id) ON DELETE CASCADE,
    email      TEXT NOT NULL CHECK (email = lower(email)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT,
    CONSTRAINT uq_early_access_invited_email UNIQUE (program_id, email)
);
CREATE INDEX idx_eaie_email ON early_access_invited_email (email);        -- sign-in probe
CREATE INDEX idx_eaie_created_at ON early_access_invited_email (created_at); -- purge sweep

-- The CSV import resolves existing accounts with WHERE lower(email) IN (...).
-- app_user.email carries only a case-SENSITIVE UNIQUE from feat_1683.sql.
CREATE INDEX idx_app_user_email_lower ON app_user (lower(email));

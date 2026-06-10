--liquibase formatted sql
--changeset liquibase:feat-1694-grants-app-role
-- Grant the application role access to all existing tables in the users DB
-- and configure default privileges so any future tables are automatically accessible.
-- The role name is injected at migration time via the Liquibase -D property flag.
-- Locally: users_app_role=postgres (same as the Liquibase user — grant is a no-op).
-- Production: users_app_role is sourced from the environment secret.

GRANT USAGE ON SCHEMA public TO ${users_app_role};

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${users_app_role};

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${users_app_role};

-- Any table created by the Liquibase user in this schema will automatically
-- be accessible to the app role — no per-migration GRANTs needed in the future.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${users_app_role};

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO ${users_app_role};

-- Issue #1789: Feature flag gating the Seal of Reliability search filter.
-- Viewing a feed's seal is public (the embedded reliability_seal object and the
-- /v1/gtfs_feeds/{id}/reliability endpoint); filtering or searching the catalogue *by* seal status
-- is restricted to selected users, who are granted the flag individually through user_feature_flag.
-- The flag row has to exist for anyone to be able to hold it: feature_flag_enabled denies when the
-- flag is missing, so without this changeset the filter would be permanently unavailable.
-- default_value is false, so creating the flag grants nothing on its own.
INSERT INTO feature_flag (id, name, description, value_type, default_value)
VALUES (
    'isSealFilterEnabled',
    'Seal of Reliability Filter',
    'Allows filtering and searching feeds by their Seal of Reliability status (the has_seal query parameter).',
    'boolean',
    'false'
)
ON CONFLICT (id) DO NOTHING;

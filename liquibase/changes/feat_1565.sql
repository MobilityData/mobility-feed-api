-- Group table for license tag taxonomies.
CREATE TABLE IF NOT EXISTS license_tag_group (
    id TEXT PRIMARY KEY,
    short_name TEXT,
    description TEXT NOT NULL
);

-- Create the license_tag table to store taxonomy tags used to classify licenses.
-- Each tag has a composite id of the form "group:tag" (e.g. "spdx:osi-approved").
CREATE TABLE IF NOT EXISTS license_tag (
    id TEXT PRIMARY KEY,
    "group" TEXT NOT NULL REFERENCES license_tag_group(id),
    tag TEXT NOT NULL,
    url TEXT,
    description TEXT,
    UNIQUE ("group", tag)
);

-- Join table for the many-to-many relationship between licenses and tags.
CREATE TABLE IF NOT EXISTS license_license_tags (
    license_id TEXT REFERENCES license(id) ON DELETE CASCADE,
    tag_id TEXT REFERENCES license_tag(id) ON DELETE CASCADE,
    PRIMARY KEY (license_id, tag_id)
);


CREATE INDEX IF NOT EXISTS ix_license_license_tags_license_id ON license_license_tags (license_id);
CREATE INDEX IF NOT EXISTS ix_license_license_tags_tag_id ON license_license_tags (tag_id);

CREATE TABLE license (
id TEXT PRIMARY KEY,
type TEXT NOT NULL CHECK (type IN ('standard', 'custom')),
is_spdx BOOLEAN NOT NULL DEFAULT FALSE,
name TEXT NOT NULL,
url TEXT,
description TEXT,
content_txt TEXT,
content_html TEXT,
created_at TIMESTAMP,
updated_at TIMESTAMP
);

-- Unified rules table
CREATE TABLE rules (
name TEXT PRIMARY KEY,
label TEXT NOT NULL,
description TEXT,
type TEXT NOT NULL CHECK (type IN ('permission', 'condition', 'limitation'))
);

-- Join table for license-rule mappings
CREATE TABLE license_rules (
license_id TEXT REFERENCES license(id) ON DELETE CASCADE,
rule_id TEXT REFERENCES rules(name) ON DELETE CASCADE,
PRIMARY KEY (license_id, rule_id)
);
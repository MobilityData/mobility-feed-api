-- A rule's identity is (name, type), not name alone: the same rule name can appear under more
-- than one category. For example "patent-use" is a permission for licenses that grant patent
-- rights and a limitation for licenses that explicitly do not (the choosealicense.com
-- convention). The original rules primary key on name alone could not represent both, causing a
-- rules_pkey unique-violation when loading the catalog.
--
-- Widen the primary key to (name, type) and make license_rules reference that composite key. The
-- table is also renamed rules -> rule for consistency with the rest of the schema (license, feed,
-- license_tag, ... are all singular) and so the generated ORM relationship keeps the name "rules".

-- 1. Drop the single-column FK from license_rules before altering the key it references.
ALTER TABLE license_rules DROP CONSTRAINT IF EXISTS license_rules_rule_id_fkey;

-- 2. Rename the table to the singular form.
ALTER TABLE rules RENAME TO rule;
ALTER TABLE rule RENAME CONSTRAINT rules_type_check TO rule_type_check;

-- 3. Widen the primary key from (name) to (name, type).
ALTER TABLE rule DROP CONSTRAINT IF EXISTS rules_pkey;
ALTER TABLE rule ADD CONSTRAINT rule_pkey PRIMARY KEY (name, type);

-- 4. Add the rule_type discriminator to the join table and backfill it from the existing rows.
--    This is safe: before this change rule names were still unique, so the join is unambiguous.
ALTER TABLE license_rules ADD COLUMN IF NOT EXISTS rule_type TEXT;
UPDATE license_rules lr
SET rule_type = r.type
FROM rule r
WHERE lr.rule_id = r.name AND lr.rule_type IS NULL;
ALTER TABLE license_rules ALTER COLUMN rule_type SET NOT NULL;

-- 5. Rebuild the join table primary key and foreign key against the composite (name, type) key.
ALTER TABLE license_rules DROP CONSTRAINT IF EXISTS license_rules_pkey;
ALTER TABLE license_rules ADD CONSTRAINT license_rules_pkey PRIMARY KEY (license_id, rule_id, rule_type);
ALTER TABLE license_rules
    ADD CONSTRAINT license_rules_rule_fkey
    FOREIGN KEY (rule_id, rule_type) REFERENCES rule (name, type) ON DELETE CASCADE;

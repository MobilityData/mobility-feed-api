ALTER TABLE feed ADD CONSTRAINT feed_stable_id_unique UNIQUE (stable_id);
-- 1. Catalog of allowed keys + optional global values
CREATE TABLE config_key (
  namespace     text        NOT NULL,              -- e.g. 'reverse_geolocation'
  key           text        NOT NULL,              -- e.g. 'country_fallback'
  description   text,
  default_value jsonb,                             -- fallback if nothing else
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (namespace, key)
);

-- 2. Per-feed overrides
CREATE TABLE config_value_feed (
  feed_stable_id       varchar(255) NOT NULL,
  namespace     text         NOT NULL,
  key           text         NOT NULL,
  value         jsonb        NOT NULL,
  updated_at    timestamptz  NOT NULL DEFAULT now(),
  PRIMARY KEY (feed_stable_id, namespace, key),
  FOREIGN KEY (namespace, key) REFERENCES config_key(namespace, key) ON DELETE CASCADE
);

-- Helpful index
CREATE INDEX config_value_feed_gin ON config_value_feed USING GIN (value);
-- Rename gtfs_dataset_changelog dataset columns from (previous, current) to (base, new)
-- so the database matches the comparer HTTP API naming (base_dataset_stable_id /
-- new_dataset_stable_id) and a single, consistent vocabulary is used everywhere
ALTER TABLE gtfs_dataset_changelog RENAME COLUMN previous_dataset_id TO base_dataset_id;
ALTER TABLE gtfs_dataset_changelog RENAME COLUMN current_dataset_id TO new_dataset_id;

ALTER TABLE gtfs_dataset_changelog
    RENAME CONSTRAINT gtfs_dataset_changelog_previous_dataset_id_fkey
    TO gtfs_dataset_changelog_base_dataset_id_fkey;
ALTER TABLE gtfs_dataset_changelog
    RENAME CONSTRAINT gtfs_dataset_changelog_current_dataset_id_fkey
    TO gtfs_dataset_changelog_new_dataset_id_fkey;
ALTER TABLE gtfs_dataset_changelog
    RENAME CONSTRAINT gtfs_dataset_changelog_previous_current_key
    TO gtfs_dataset_changelog_base_new_key;

ALTER INDEX idx_gtfs_dataset_changelog_current RENAME TO idx_gtfs_dataset_changelog_new;

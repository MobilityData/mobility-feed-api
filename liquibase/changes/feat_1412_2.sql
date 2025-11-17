-- This scripts fixes the default value of feed.created_at. The column created_at was defaulting to'2024-02-08 00:00:00.000000' instead of NOW.
ALTER TABLE Feed ALTER COLUMN created_at SET DEFAULT NOW();

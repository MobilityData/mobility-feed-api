-- Drop old columns if they exist (cleanup for consistency / schema reset)
ALTER TABLE Gtfsfeed DROP COLUMN IF EXISTS visualization_dataset_id;
ALTER TABLE Gtfsfeed DROP COLUMN IF EXISTS bounding_box_dataset_id;
ALTER TABLE Gtfsfeed DROP COLUMN IF EXISTS bounding_box;

-- Add new columns with proper definitions
-- visualization_dataset_id: references the dataset used for UI/visualization
ALTER TABLE Gtfsfeed
  ADD COLUMN visualization_dataset_id VARCHAR(255) REFERENCES Gtfsdataset(id);

-- bounding_box_dataset_id: references the dataset that provided the bounding box
ALTER TABLE Gtfsfeed
  ADD COLUMN bounding_box_dataset_id VARCHAR(255) REFERENCES Gtfsdataset(id);

-- bounding_box: stores the geometry for the feed’s bounding box (WGS84 / SRID 4326)
ALTER TABLE Gtfsfeed
  ADD COLUMN bounding_box geometry(Polygon, 4326);

-- Populate the bounding box info
-- For each feed, find the most recent dataset that has a bounding box
-- (ROW_NUMBER() = 1 keeps only the latest per feed_id)
WITH latest AS (
  SELECT
    id,
    feed_id,
    bounding_box,
    ROW_NUMBER() OVER (
      PARTITION BY feed_id
      ORDER BY downloaded_at DESC NULLS LAST, id DESC
    ) AS rn
  FROM Gtfsdataset
  WHERE bounding_box IS NOT NULL
)
UPDATE Gtfsfeed gf
SET
  bounding_box_dataset_id = l.id,       -- link feed to the chosen dataset
  bounding_box            = l.bounding_box -- copy its bounding box geometry
FROM latest l
WHERE l.rn = 1                          -- keep only the latest dataset per feed
  AND gf.id = l.feed_id;                -- match feed with its dataset


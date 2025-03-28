-- Index to improve the filtering by feed_id and downloaded_at
CREATE INDEX idx_gtfsdataset_feed_id_downloaded_at_desc ON GTFSDataset(feed_id, downloaded_at DESC);

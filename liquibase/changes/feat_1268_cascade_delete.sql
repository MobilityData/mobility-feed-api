-- liquibase formatted sql

-- changeset mobilitydata:1268-gtfsrealtimefeed
ALTER TABLE GTFSRealtimeFeed DROP CONSTRAINT IF EXISTS gtfsrealtimefeed_id_fkey;
ALTER TABLE GTFSRealtimeFeed
ADD CONSTRAINT gtfsrealtimefeed_id_fkey
FOREIGN KEY (id) REFERENCES Feed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-gtfsfeed
ALTER TABLE GTFSFeed DROP CONSTRAINT IF EXISTS gtfsfeed_id_fkey;
ALTER TABLE GTFSFeed
ADD CONSTRAINT gtfsfeed_id_fkey
FOREIGN KEY (id) REFERENCES Feed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-gtfsdataset
ALTER TABLE GTFSDataset DROP CONSTRAINT IF EXISTS gtfsdataset_feed_id_fkey;
ALTER TABLE GTFSDataset
ADD CONSTRAINT gtfsdataset_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES Feed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-redirectingid-source
ALTER TABLE RedirectingID DROP CONSTRAINT IF EXISTS redirectingid_source_id_fkey;
ALTER TABLE RedirectingID
ADD CONSTRAINT redirectingid_source_id_fkey
FOREIGN KEY (source_id) REFERENCES Feed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-redirectingid-target
ALTER TABLE RedirectingID DROP CONSTRAINT IF EXISTS redirectingid_target_id_fkey;
ALTER TABLE RedirectingID
ADD CONSTRAINT redirectingid_target_id_fkey
FOREIGN KEY (target_id) REFERENCES Feed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-entitytypefeed
ALTER TABLE EntityTypeFeed DROP CONSTRAINT IF EXISTS entitytypefeed_feed_id_fkey;
ALTER TABLE EntityTypeFeed
ADD CONSTRAINT entitytypefeed_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES GTFSRealtimeFeed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-feedreference-gtfsrt
ALTER TABLE FeedReference DROP CONSTRAINT IF EXISTS feedreference_gtfs_rt_feed_id_fkey;
ALTER TABLE FeedReference
ADD CONSTRAINT feedreference_gtfs_rt_feed_id_fkey
FOREIGN KEY (gtfs_rt_feed_id) REFERENCES GTFSRealtimeFeed(id) ON DELETE CASCADE;

-- changeset mobilitydata:1268-feedreference-gtfs
ALTER TABLE FeedReference DROP CONSTRAINT IF EXISTS feedreference_gtfs_feed_id_fkey;
ALTER TABLE FeedReference
ADD CONSTRAINT feedreference_gtfs_feed_id_fkey
FOREIGN KEY (gtfs_feed_id) REFERENCES GTFSFeed(id) ON DELETE CASCADE;

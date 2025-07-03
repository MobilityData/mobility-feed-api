-- These changes are to enable cascading deletes for various foreign key constraints in the database.
--
ALTER TABLE EntityTypeFeed DROP CONSTRAINT IF EXISTS entitytypefeed_feed_id_fkey;
ALTER TABLE EntityTypeFeed
ADD CONSTRAINT entitytypefeed_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES GTFSRealtimeFeed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE ExternalID DROP CONSTRAINT IF EXISTS externalid_feed_id_fkey;
ALTER TABLE ExternalID
ADD CONSTRAINT externalid_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES Feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeatureValidationReport DROP CONSTRAINT IF EXISTS featurevalidationreport_validation_id_fkey;
ALTER TABLE FeatureValidationReport
ADD CONSTRAINT featurevalidationreport_validation_id_fkey
FOREIGN KEY (validation_id) REFERENCES ValidationReport(id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeedOSMLocationGroup DROP CONSTRAINT IF EXISTS feedosmlocation_feed_id_fkey;
ALTER TABLE FeedOSMLocationGroup
ADD CONSTRAINT feedosmlocation_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES Feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeedOSMLocationGroup DROP CONSTRAINT IF EXISTS feedosmlocation_group_id_fkey;
ALTER TABLE FeedOSMLocationGroup
ADD CONSTRAINT feedosmlocation_group_id_fkey
FOREIGN KEY (group_id) REFERENCES osmlocationgroup(group_id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeedReference DROP CONSTRAINT IF EXISTS feedreference_gtfs_feed_id_fkey;
ALTER TABLE FeedReference
ADD CONSTRAINT feedreference_gtfs_feed_id_fkey
FOREIGN KEY (gtfs_feed_id) REFERENCES public.gtfsfeed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeedReference DROP CONSTRAINT IF EXISTS feedreference_gtfs_rt_feed_id_fkey;
ALTER TABLE FeedReference
ADD CONSTRAINT feedreference_gtfs_rt_feed_id_fkey
FOREIGN KEY (gtfs_rt_feed_id) REFERENCES public.gtfsrealtimefeed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE GtfsFeed DROP CONSTRAINT IF EXISTS gtfsfeed_id_fkey;
ALTER TABLE GtfsFeed
ADD CONSTRAINT gtfsfeed_id_fkey
FOREIGN KEY (id) REFERENCES public.feed(id) ON DELETE CASCADE;

--
ALTER TABLE GtfsDataset DROP CONSTRAINT IF EXISTS gtfsdataset_feed_id_fkey;
ALTER TABLE GtfsDataset
ADD CONSTRAINT gtfsdataset_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES public.feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE GTFSRealtimeFeed DROP CONSTRAINT IF EXISTS gtfsrealtimefeed_id_fkey;
ALTER TABLE GTFSRealtimeFeed
ADD CONSTRAINT gtfsrealtimefeed_id_fkey
FOREIGN KEY (id) REFERENCES public.feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE Location_GtfsDataset DROP CONSTRAINT IF EXISTS location_gtfsdataset_gtfsdataset_id_fkey;
ALTER TABLE Location_GtfsDataset
ADD CONSTRAINT location_gtfsdataset_gtfsdataset_id_fkey
FOREIGN KEY (gtfsdataset_id) REFERENCES public.gtfsdataset(id) ON DELETE CASCADE;

--                                             
ALTER TABLE Location_GtfsDataset DROP CONSTRAINT IF EXISTS location_gtfsdataset_location_id_fkey;
ALTER TABLE Location_GtfsDataset
ADD CONSTRAINT location_gtfsdataset_location_id_fkey
FOREIGN KEY (location_id) REFERENCES public.location(id) ON DELETE CASCADE;

--                                             
ALTER TABLE LocationFeed DROP CONSTRAINT IF EXISTS locationfeed_feed_id_fkey;
ALTER TABLE LocationFeed
ADD CONSTRAINT locationfeed_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES public.feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE LocationFeed DROP CONSTRAINT IF EXISTS locationfeed_location_id_fkey;
ALTER TABLE LocationFeed
ADD CONSTRAINT locationfeed_location_id_fkey
FOREIGN KEY (location_id) REFERENCES public.location(id) ON DELETE CASCADE;

--                                             
ALTER TABLE Notice DROP CONSTRAINT IF EXISTS notice_validation_report_id_fkey;
ALTER TABLE Notice
ADD CONSTRAINT notice_validation_report_id_fkey
FOREIGN KEY (validation_report_id) REFERENCES public.validationreport(id) ON DELETE CASCADE;

ALTER TABLE Notice DROP CONSTRAINT IF EXISTS notice_dataset_id_fkey;
ALTER TABLE Notice
ADD CONSTRAINT notice_dataset_id_fkey
FOREIGN KEY (dataset_id) REFERENCES public.gtfsdataset(id) ON DELETE CASCADE;

--                                             
ALTER TABLE OfficialStatusHistory DROP CONSTRAINT IF EXISTS officialstatushistory_feed_id_fkey;
ALTER TABLE OfficialStatusHistory
ADD CONSTRAINT officialstatushistory_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES public.feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE OsmLocationGroupGeopolygon DROP CONSTRAINT IF EXISTS osmlocationgroupgeopolygon_group_id_fkey;
ALTER TABLE OsmLocationGroupGeopolygon
ADD CONSTRAINT osmlocationgroupgeopolygon_group_id_fkey
FOREIGN KEY (group_id) REFERENCES public.osmlocationgroup(group_id) ON DELETE CASCADE;

--                                             
ALTER TABLE OsmLocationGroupGeopolygon DROP CONSTRAINT IF EXISTS osmlocationgroupgeopolygon_osm_id_fkey;
ALTER TABLE OsmLocationGroupGeopolygon
ADD CONSTRAINT osmlocationgroupgeopolygon_osm_id_fkey
FOREIGN KEY (osm_id) REFERENCES public.geopolygon(osm_id) ON DELETE CASCADE;

--
ALTER TABLE RedirectingID DROP CONSTRAINT IF EXISTS redirectingid_source_id_fkey;
ALTER TABLE RedirectingID
ADD CONSTRAINT redirectingid_source_id_fkey
FOREIGN KEY (source_id) REFERENCES Feed(id) ON DELETE CASCADE;

--
ALTER TABLE RedirectingID DROP CONSTRAINT IF EXISTS redirectingid_target_id_fkey;
ALTER TABLE RedirectingID
ADD CONSTRAINT redirectingid_target_id_fkey
FOREIGN KEY (target_id) REFERENCES Feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeedLocationGroupPoint DROP CONSTRAINT IF EXISTS stop_feed_id_fkey;
ALTER TABLE FeedLocationGroupPoint
ADD CONSTRAINT stop_feed_id_fkey
FOREIGN KEY (feed_id) REFERENCES public.feed(id) ON DELETE CASCADE;

--                                             
ALTER TABLE FeedLocationGroupPoint DROP CONSTRAINT IF EXISTS stop_group_id_fkey;
ALTER TABLE FeedLocationGroupPoint
ADD CONSTRAINT stop_group_id_fkey
FOREIGN KEY (group_id) REFERENCES public.osmlocationgroup(group_id) ON DELETE CASCADE;

--                                             
ALTER TABLE ValidationReportGTFSDataset DROP CONSTRAINT IF EXISTS validationreportgtfsdataset_dataset_id_fkey;
ALTER TABLE ValidationReportGTFSDataset
ADD CONSTRAINT validationreportgtfsdataset_dataset_id_fkey
FOREIGN KEY (dataset_id) REFERENCES public.gtfsdataset(id) ON DELETE CASCADE;

--                                             
ALTER TABLE ValidationReportGTFSDataset DROP CONSTRAINT IF EXISTS validationreportgtfsdataset_validation_report_id_fkey;
ALTER TABLE ValidationReportGTFSDataset
ADD CONSTRAINT validationreportgtfsdataset_validation_report_id_fkey
FOREIGN KEY (validation_report_id) REFERENCES public.validationreport(id) ON DELETE CASCADE;

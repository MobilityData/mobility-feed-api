-- Feed
CREATE INDEX idx_feed_id ON Feed(id);
CREATE INDEX idx_feed_status ON Feed(status);
CREATE INDEX idx_feed_provider_stable_id ON Feed(provider, stable_id);

-- GTFSDataset 
CREATE INDEX idx_gtfsdataset_feed_id ON GTFSDataset(feed_id);
CREATE INDEX idx_gtfsdataset_latest ON GTFSDataset(latest);

-- LocationFeed
CREATE INDEX idx_locationfeed_feed_id ON LocationFeed(feed_id);
CREATE INDEX idx_locationfeed_location_id ON LocationFeed(location_id);

-- ValidationReport
CREATE INDEX idx_validationreport_validator_version ON ValidationReport(validator_version);

-- ValidationReportGTFSDataset
CREATE INDEX idx_vrgtfsdataset_dataset_id ON ValidationReportGTFSDataset(dataset_id);
CREATE INDEX idx_vrgtfsdataset_report_id ON ValidationReportGTFSDataset(validation_report_id);




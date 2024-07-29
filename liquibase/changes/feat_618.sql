ALTER TABLE Location
ADD COLUMN country VARCHAR(255);

-- Create the join table Location_GtfsDataset
CREATE TABLE Location_GTFSDataset (
    location_id VARCHAR(255) NOT NULL,
    gtfsdataset_id VARCHAR(255) NOT NULL,
    PRIMARY KEY (location_id, gtfsdataset_id),
    FOREIGN KEY (location_id) REFERENCES Location(id),
    FOREIGN KEY (gtfsdataset_id) REFERENCES GtfsDataset(id)
);

-- 1. Add Table ValidationReport
CREATE TABLE ValidationReport (
    id VARCHAR(255) PRIMARY KEY,
    dataset_id VARCHAR(255) REFERENCES GTFSDataset(id),
    version VARCHAR(255)
);

-- 2. Modify Table GTFSDataset to add FK to ValidationReport
ALTER TABLE GTFSDataset
ADD COLUMN latest_validation_report VARCHAR(255) REFERENCES ValidationReport(id);

-- 3. Create custom type for severity
CREATE TYPE severity_type AS ENUM ('ERROR', 'WARNING', 'INFO');

-- 4. Add Table Notice
CREATE TABLE Notice (
    dataset_id VARCHAR(255) REFERENCES GTFSDataset(id),
    validation_report_id VARCHAR(255) REFERENCES ValidationReport(id),
    notice_code VARCHAR(255),
    severity severity_type,
    PRIMARY KEY (dataset_id, validation_report_id, notice_code)
);

-- 5. Add indexes for the Notice table
CREATE INDEX idx_notice_dataset_id ON Notice(dataset_id);
CREATE INDEX idx_notice_dataset_id_validation_id ON Notice(dataset_id, validation_report_id);

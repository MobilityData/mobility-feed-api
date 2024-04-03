ALTER TABLE Component
  RENAME TO Feature;
DROP TABLE ComponentGtfsDataset;

CREATE TABLE FeatureValidationReport (
    feature VARCHAR(255) REFERENCES Feature(name),
    validation_id VARCHAR(255) REFERENCES ValidationReport(id),
    PRIMARY KEY (feature, validation_id)
);
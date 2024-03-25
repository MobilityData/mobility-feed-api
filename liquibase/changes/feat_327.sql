ALTER TABLE component
  RENAME TO feature;
DROP TABLE componentgtfsdataset;

CREATE TABLE FeatureValidationReport (
    feature VARCHAR(255) REFERENCES Feature(name),
    validation_id VARCHAR(255) REFERENCES ValidationReport(id),
    PRIMARY KEY (feature, validation_id)
);
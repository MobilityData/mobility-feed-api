ALTER TABLE ValidationReport
ADD COLUMN validated_at TIMESTAMP,
ADD COLUMN html_report VARCHAR(255),
ADD COLUMN json_report VARCHAR(255);
ALTER TABLE validationreport
ADD COLUMN total_error INT DEFAULT 0,
ADD COLUMN total_warning INT DEFAULT 0,
ADD COLUMN total_info INT DEFAULT 0,
ADD COLUMN unique_error_count INT DEFAULT 0,
ADD COLUMN unique_warning_count INT DEFAULT 0,
ADD COLUMN unique_info_count INT DEFAULT 0;
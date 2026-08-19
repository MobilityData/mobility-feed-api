-- Drop leftover ad-hoc analysis tables.
-- These were incorrectly created for one-off for feed coverage mapping
-- they are not part of the managed schema and are not
-- referenced by the API, the Cloud Functions, or any materialized view.

DROP TABLE IF EXISTS global_coverage_1_20260513205122;
DROP TABLE IF EXISTS global_coverage_2_20260513205110;
DROP TABLE IF EXISTS global_coverage_3_20260513205102;
DROP TABLE IF EXISTS global_coverage_4_20260513205053;
DROP TABLE IF EXISTS global_coverage_5_20260513205044;
DROP TABLE IF EXISTS global_coverage_6_20260513205035;
DROP TABLE IF EXISTS global_coverage_7_20260513205024;
DROP TABLE IF EXISTS global_coverage_8_20260513205015;
DROP TABLE IF EXISTS global_coverage_9_20260513204956;
DROP TABLE IF EXISTS global_coverage_10_20260513204943;
DROP TABLE IF EXISTS feed_city_50_cities_20260513180501;
DROP TABLE IF EXISTS feed_city_50_cities_20260513153811;

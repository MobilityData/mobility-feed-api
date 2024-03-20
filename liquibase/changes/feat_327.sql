ALTER TABLE component
  RENAME TO feature;
ALTER TABLE componentgtfsdataset
  RENAME TO featuregtfsdataset;
ALTER TABLE featuregtfsdataset
  RENAME COLUMN component to feature;
ALTER TABLE featuregtfsdataset
  RENAME CONSTRAINT componentgtfsdataset_pkey TO featuregtfsdataset_pkey;
  
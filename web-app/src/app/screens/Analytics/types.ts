import { type EntityLocations } from '../../services/feeds/utils';

export interface Notices {
  errors: string[];
  warnings: string[];
  infos: string[];
}

export interface GTFSFeedMetrics {
  feed_id: string;
  dataset_id: string;
  notices: Notices;
  features: string[];
  created_on: Date;
  last_modified: Date;
  locations: EntityLocations;
  locations_string: string;
  provider: string;
  metrics?: GTFSMetrics;
}

export interface GTFSMetrics {
  feed_id: string;
  computed_on: Date[];
  errors_count: number[];
  warnings_count: number[];
  infos_count: number[];
}

export interface NoticeMetrics {
  notice: string;
  severity: string;
  computed_on: Date[];
  feeds_count: number[];
  latest_feed_count: number;
}

export interface FeatureMetrics {
  feature: string;
  computed_on: Date[];
  feeds_count: number[];
  latest_feed_count: number;
  feature_group?: string; // Add a property to handle feature grouping
  feature_sub_group?: string;
}

export interface AnalyticsFile {
  file_name: string;
  created_on: Date;
}

export interface GBFSNotice {
  keyword: string;
  gbfs_file: string;
  schema_path: string;
  count: number;
}

export interface GBFSFeedMetrics {
  feed_id: string;
  snapshot_id: string;
  system_id: string;
  auto_discovery_url: string;
  snapshot_hosted_url: string;
  notices: GBFSNotice[];
  versions: string[];
  created_on: string;
  operator: string;
  locations: EntityLocations;
  locations_string: string;
  metrics?: GBFSMetrics;
}

export interface GBFSMetrics {
  feed_id: string;
  snapshot_id: string;
  computed_on: Date[];
  errors_count: number[];
}

export interface GBFSNoticeMetrics {
  keyword: string;
  gbfs_file: string;
  schema_path: string;
  computed_on: Date[];
  feeds_count: number[];
}

export interface GBFSVersionMetrics {
  version: string;
  computed_on: Date[];
  feeds_count: number[];
}

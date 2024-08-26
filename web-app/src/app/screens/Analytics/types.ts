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
  metrics?: Metrics;
}

export interface Metrics {
  feed_id: string;
  computed_on: string[];
  errors_count: number[];
  warnings_count: number[];
  infos_count: number[];
}

export interface NoticeMetrics {
  notice: string;
  severity: string;
  computed_on: string[];
  feeds_count: number[];
  latest_feed_count: number;
}

export interface FeatureMetrics {
  feature: string;
  computed_on: string[];
  feeds_count: number[];
  latest_feed_count: number;
  feature_group?: string; // Add a property to handle feature grouping
}

export interface AnalyticsFile {
  file_name: string;
  created_on: string;
}

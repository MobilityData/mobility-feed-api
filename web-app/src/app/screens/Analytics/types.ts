export interface Notices {
  errors: string[];
  warnings: string[];
  infos: string[];
}

export interface Feed {
  feed_id: string;
  dataset_id: string;
  notices: Notices;
  features: string[];
  created_on: Date;
  last_modified: Date;
  country_code: string;
  country: string;
  subdivision_name: string;
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

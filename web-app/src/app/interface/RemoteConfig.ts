import { remoteConfig } from '../../firebase';

type FirebaseDefaultConfig = typeof remoteConfig.defaultConfig;

export interface BypassConfig {
  regex: string[];
}

export interface RemoteConfigValues extends FirebaseDefaultConfig {
  enableAppleSSO: boolean;
  enableFeedsPage: boolean;
  enableLanguageToggle: boolean;
  /**
   * Enables the feed submission stepper
   * Values:
   *  true: renders the feed submission stepper based in the FeedSubmissionStepper.tsx
   *  false: renders the legacy feed submission page based in the Contribute.tsx
   */
  enableFeedSubmissionStepper: boolean;
  /** Enable Metrics view
   * Values:
   * true: renders the metrics view
   * false: hides the metrics view
   */
  enableMetrics: boolean;
  /** GTFS metrics' bucket endpoint */
  gtfsMetricsBucketEndpoint: string;
  /** GBFS metrics' bucket endpoint */
  gbfsMetricsBucketEndpoint: string;
  featureFlagBypass: string;
  enableFeatureFilterSearch: boolean;
  enableIsOfficialFilterSearch: boolean;
  enableFeedStatusBadge: boolean;
  enableGbfsInSearchPage: boolean;
}

const featureByPassDefault: BypassConfig = {
  regex: [],
};

// Add default values for remote config here
export const defaultRemoteConfigValues: RemoteConfigValues = {
  enableAppleSSO: false,
  enableFeedsPage: false,
  enableLanguageToggle: false,
  enableFeedSubmissionStepper: false,
  enableMetrics: false,
  gtfsMetricsBucketEndpoint:
    'https://storage.googleapis.com/mobilitydata-gtfs-analytics-dev',
  gbfsMetricsBucketEndpoint:
    'https://storage.googleapis.com/mobilitydata-gbfs-analytics-dev',
  featureFlagBypass: JSON.stringify(featureByPassDefault),
  enableFeatureFilterSearch: false,
  enableIsOfficialFilterSearch: false,
  enableFeedStatusBadge: false,
  enableGbfsInSearchPage: false,
};

remoteConfig.defaultConfig = defaultRemoteConfigValues;

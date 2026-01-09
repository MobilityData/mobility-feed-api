import { remoteConfig } from '../../firebase';

type FirebaseDefaultConfig = typeof remoteConfig.defaultConfig;

export interface BypassConfig {
  regex: string[];
}

export type GbfsVersionConfig = string[];

export interface RemoteConfigValues extends FirebaseDefaultConfig {
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
  gbfsVersions: string;
  enableGtfsVisualizationMap: boolean;

  /** Max number of data stuff to display on top of the map to avoid overflow */
  visualizationMapPreviewDataLimit: number;
  visualizationMapFullDataLimit: number;

  // This feature flag enable or the coovered area component with expected behavior:
  // 1- hides/shows the toggle button for gtfs feeds
  // 2- use bounding box view for GBFS instead of full covered area map
  enableDetailedCoveredArea: boolean;
  gbfsValidator: boolean;
}

const featureByPassDefault: BypassConfig = {
  regex: [],
};

const gbfsVersionsDefault: GbfsVersionConfig = [];

// Add default values for remote config here
export const defaultRemoteConfigValues: RemoteConfigValues = {
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
  enableGbfsInSearchPage: true,
  gbfsVersions: JSON.stringify(gbfsVersionsDefault),
  enableGtfsVisualizationMap: false,
  visualizationMapFullDataLimit: 5,
  visualizationMapPreviewDataLimit: 3,
  enableDetailedCoveredArea: false,
  gbfsValidator: false,
};

remoteConfig.defaultConfig = defaultRemoteConfigValues;

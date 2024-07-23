import { remoteConfig } from '../../firebase';

type FirebaseDefaultConfig = typeof remoteConfig.defaultConfig;

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
}

// Add default values for remote config here
export const defaultRemoteConfigValues: RemoteConfigValues = {
  enableAppleSSO: false,
  enableFeedsPage: false,
  enableLanguageToggle: false,
  enableFeedSubmissionStepper: false,
};

remoteConfig.defaultConfig = defaultRemoteConfigValues;

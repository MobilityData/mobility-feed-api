import { remoteConfig } from '../../firebase';

type FirebaseDefaultConfig = typeof remoteConfig.defaultConfig;

export interface RemoteConfigValues extends FirebaseDefaultConfig {
  enableAppleSSO: boolean;
  enableMVPSearch: boolean;
  enableFeedsPage: boolean;
  enableLanguageToggle: boolean;
}

// Add default values for remote config here
export const defaultRemoteConfigValues: RemoteConfigValues = {
  enableAppleSSO: false,
  enableMVPSearch: false,
  enableFeedsPage: false,
  enableLanguageToggle: false,
};

remoteConfig.defaultConfig = defaultRemoteConfigValues;

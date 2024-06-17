import { remoteConfig } from '../../firebase';
export type RemoteConfigValues = Record<string, string | number | boolean>;

// Add default values for remote config here
export const defaultRemoteConfigValues: RemoteConfigValues = {
  enableAppleSSO: false,
  enableMVPSearch: false,
  enableFeedsPage: false,
};

remoteConfig.defaultConfig = defaultRemoteConfigValues;

import {
  defaultRemoteConfigValues,
  type RemoteConfigValues,
} from '../interface/RemoteConfig';
import { buildNavigationItems } from './Navigation';

jest.mock('firebase/compat/app', () => ({
  initializeApp: jest.fn(),
  remoteConfig: jest.fn(() => ({
    settings: { minimumFetchIntervalMillis: 3600000 },
  })),
}));

describe('Navigation Elements', () => {
  it('should return feed nav item if feature flag enabled', () => {
    const featureFlags: RemoteConfigValues = {
      ...defaultRemoteConfigValues,
    };
    const navigationItems = buildNavigationItems(featureFlags);
    const feedsNavigation = navigationItems.find(
      (item) => item.title === 'Feeds',
    );
    expect(feedsNavigation).toBeDefined();
  });
});

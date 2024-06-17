import { buildNavigationItems } from "./Navigation";

describe('Navigation Elements', () => {
  describe('building navigation items', () => {
    it('should return feed nav item if feature flag enabled', () => {
        const featureFlags = {
            enableFeedsPage: true
        }
        const navigationItems = buildNavigationItems(featureFlags);
        const feedsNavigation = navigationItems.find(item => item.title === 'Feeds');
        expect(feedsNavigation).toBeDefined();
    });

    it('should not return feed nav item if feature flag disabled', () => {
        const featureFlags = {
            enableFeedsPage: false
        }
        const navigationItems = buildNavigationItems(featureFlags);
        const feedsNavigation = navigationItems.find(item => item.title === 'Feeds');
        expect(feedsNavigation).toBeUndefined();
    });
  });


});

import type NavigationItem from '../interface/Navigation';
import { type RemoteConfigValues } from '../interface/RemoteConfig';

export const SIGN_OUT_TARGET = '/';
export const SIGN_IN_TARGET = '/sign-in';
export const ACCOUNT_TARGET = '/account';
export const ADD_FEED_TARGET = '/contribute';
export const POST_REGISTRATION_TARGET = '/verify-email';
export const COMPLETE_REGISTRATION_TARGET = '/complete-registration';

export const MOBILITY_DATA_LINKS = {
  twitter: 'https://twitter.com/mobilitydataio',
  slack:
    'https://share.mobilitydata.org/slack?_gl=1*vdltzn*_ga*MTg3NTkzMjk0MS4xNjg1NDA4NDQ5*_ga_55GPMF0W9Z*MTY5NzIxNDMzMS4xNy4wLjE2OTcyMTQzMzIuMC4wLjA.*_ga_38D0062PPR*MTY5NzIxNDMzMS43LjAuMTY5NzIxNDMzMS4wLjAuMA..&_ga=2.58702697.2112403184.1697214331-1875932941.1685408449',
  linkedin: 'https://www.linkedin.com/company/mobilitydata/',
  github: 'https://github.com/MobilityData/mobility-database-catalogs',
};

export function buildNavigationItems(
  featureFlags: RemoteConfigValues,
): NavigationItem[] {
  const navigationItems: NavigationItem[] = [
    {
      title: 'About',
      target: 'about',
      color: 'inherit',
    },
  ];

  if (featureFlags.enableFeedsPage) {
    navigationItems.push({
      title: 'Feeds',
      target: 'feeds',
      color: 'inherit',
    });
  }

  navigationItems.push(
    ...[
      {
        title: 'FAQ',
        target: 'faq',
        color: 'inherit',
      },
      {
        title: 'Add a Feed',
        target: 'contribute',
        color: 'inherit',
      },
      {
        title: 'API Docs',
        target:
          'https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html',
        color: 'inherit',
        external: true,
      },
      {
        title: 'Contact Us',
        target: 'mailto:api@mobilitydata.org',
        color: 'inherit',
        external: true,
      },
    ],
  );
  return navigationItems;
}

export const navigationAccountItem: NavigationItem = {
  title: 'Account',
  target: ACCOUNT_TARGET,
  color: 'inherit',
};

export type NavigationHandler = (navigationItem: NavigationItem) => void;

import type NavigationItem from '../interface/Navigation';

export const SIGN_OUT_TARGET = '/sign-out';
export const SIGN_IN_TARGET = '/sign-in';
export const ACCOUNT_TARGET = '/account';
export const COMPLETE_REGISTRATION_TARGET = '/complete-registration';

export const MOBILITY_DATA_LINKS = {
  twitter: 'https://twitter.com/mobilitydataio',
  slack:
    'https://share.mobilitydata.org/slack?_gl=1*vdltzn*_ga*MTg3NTkzMjk0MS4xNjg1NDA4NDQ5*_ga_55GPMF0W9Z*MTY5NzIxNDMzMS4xNy4wLjE2OTcyMTQzMzIuMC4wLjA.*_ga_38D0062PPR*MTY5NzIxNDMzMS43LjAuMTY5NzIxNDMzMS4wLjAuMA..&_ga=2.58702697.2112403184.1697214331-1875932941.1685408449',
  linkedin: 'https://www.linkedin.com/company/mobilitydata/',
  github: 'https://github.com/MobilityData/mobility-database-catalogs',
};

export const navigationItems: NavigationItem[] = [
  { title: 'About', target: 'about', color: 'inherit', variant: 'text' },
  { title: 'API Docs', target: 'api', color: 'inherit', variant: 'text' },
  {
    title: 'Contribute',
    target: 'contribute',
    color: 'inherit',
    variant: 'text',
  },
  {
    title: 'Contact Us',
    target: 'contact-us',
    color: 'inherit',
    variant: 'text',
  },
];

export const navigationSignoutItem: NavigationItem = {
  title: 'Sign Out',
  target: SIGN_OUT_TARGET,
  color: 'inherit',
  variant: 'text',
};
export const navigationHelpItem: NavigationItem = {
  title: 'Help',
  target: 'help', // TODO generate help page
  color: 'inherit',
  variant: 'text',
};

export const navigationAccountItem: NavigationItem = {
  title: 'Account',
  target: ACCOUNT_TARGET,
  color: 'inherit',
  variant: 'text',
};

export type NavigationHandler = (navigationItem: NavigationItem) => void;

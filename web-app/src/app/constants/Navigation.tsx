import type NavigationItem from '../interface/Navigation';

export const SIGN_OUT_TARGET = 'sign-out';
export const SIGN_IN_TARGET = 'sign-in';

const baseNavigationItems: NavigationItem[] = [
  { title: 'About', target: 'about', color: 'inherit', variant: 'text' },
  {
    title: 'Add/Update a Feed',
    target: 'add-a-feed',
    color: 'inherit',
    variant: 'text',
  },
  { title: 'API', target: 'api', color: 'inherit', variant: 'text' },
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

const authenticatedNavigationItems: NavigationItem[] = [
  ...baseNavigationItems,
  { title: 'Account', target: 'account', color: 'inherit', variant: 'text' },
  {
    title: 'Sign Out',
    target: SIGN_OUT_TARGET,
    color: 'primary',
    variant: 'contained',
  },
];

const unauthenticatedNavigationItems: NavigationItem[] = [
  ...baseNavigationItems,
  {
    title: 'Sign In',
    target: SIGN_IN_TARGET,
    color: 'primary',
    variant: 'contained',
  },
];

export const navigationItems = (isAuthenticated: boolean): NavigationItem[] => {
  return isAuthenticated
    ? authenticatedNavigationItems
    : unauthenticatedNavigationItems;
};

export type NavigationHandler = (navigationItem: NavigationItem) => void;

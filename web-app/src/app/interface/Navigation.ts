export default interface NavigationItem {
  title: string;
  color: string;
  target: string;
  variant: NavigationItemVariant;
  external?: boolean;
}

export enum NavigationItemVariant {
  Text = 'text',
  Outlined = 'outlined',
  Contained = 'contained',
}

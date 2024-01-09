export default interface NavigationItem {
  title: string;
  color: string;
  target: string;
  variant: 'text' | 'outlined' | 'contained' | undefined;
  external?: boolean;
}

export const locales = ['en', 'fr'] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = 'en';

// Subdomain to locale mapping
export const subdomainToLocale: Record<string, Locale> = {
  fr: 'fr',
};

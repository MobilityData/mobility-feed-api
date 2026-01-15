import { type NextRequest, NextResponse } from 'next/server';
import { subdomainToLocale, defaultLocale } from './i18n/config';

export function proxy(request: NextRequest): NextResponse {
  const hostname = request.headers.get('host') ?? '';
  const subdomain = hostname.split('.')[0];

  // Determine locale from subdomain (fr.mobilitydata.org → 'fr')
  const locale = subdomainToLocale[subdomain] ?? defaultLocale;

  // Set locale in cookie for server components to read
  const response = NextResponse.next();
  response.cookies.set('NEXT_LOCALE', locale);

  return response;
}

export const config = {
  matcher: ['/((?!api|_next|.*\\..*).*)'],
};

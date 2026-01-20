/**
 * Next.js Instrumentation for MSW (Mock Service Worker)
 *
 * This file enables API mocking during e2e tests by intercepting
 * server-side fetch requests.
 *
 * MSW is only enabled when NEXT_PUBLIC_API_MOCKING is set to 'enabled'
 */

export async function register() {
  if (process.env.NEXT_PUBLIC_API_MOCKING === 'enabled') {
    if (process.env.NEXT_RUNTIME === 'nodejs') {
      const { server } = await import('./mocks/server');
      server.listen({
        onUnhandledRequest: 'bypass', // Don't warn about unhandled requests
      });
      console.log('🔶 MSW Server started for API mocking');
    }
  }
}

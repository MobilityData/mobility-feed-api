import * as Sentry from '@sentry/react';
import packageJson from '../package.json';
import * as React from 'react';
import { createRoutesFromChildren, matchRoutes } from 'react-router-dom';

// Helper to safely parse Sentry sample rates from environment variables
const parseSampleRate = (value: string | undefined, defaultValue: number): number => {
  const parsed = parseFloat(value ?? String(defaultValue));
  if (isNaN(parsed) || parsed < 0 || parsed > 1) {
    return defaultValue;
  }
  return parsed;
};

const dsn = process.env.REACT_APP_SENTRY_DSN || '';
const environment =
  process.env.REACT_APP_FIREBASE_PROJECT_ID || process.env.NODE_ENV || "mobility-feeds-dev";
const release = packageJson.version;
const tracesSampleRate = parseSampleRate(
  process.env.REACT_APP_SENTRY_TRACES_SAMPLE_RATE,
  0.05,
);
const replaysSessionSampleRate = parseSampleRate(
  process.env.REACT_APP_SENTRY_REPLAY_SESSION_SAMPLE_RATE,
  0.0,
);
const replaysOnErrorSampleRate = parseSampleRate(
  process.env.REACT_APP_SENTRY_REPLAY_ERROR_SAMPLE_RATE,
  1.0,
);

if (dsn) {
  // Prefer dedicated react-router v6 integration if available, else fall back to generic browser tracing with manual routing instrumentation.
  const routerTracingIntegration =
    (Sentry as any).reactRouterV6BrowserTracingIntegration?.({
      useEffect: React.useEffect,
      reactRouterV6: { createRoutesFromChildren, matchRoutes },
    }) ||
    (Sentry as any).browserTracingIntegration?.({
      routingInstrumentation: (Sentry as any).reactRouterV6Instrumentation?.(
        React.useEffect,
        true,
        createRoutesFromChildren,
        matchRoutes,
      ),
    });

  Sentry.init({
    dsn,
    environment,
    release,
    integrations: [
      routerTracingIntegration,
      (Sentry as any).replayIntegration?.(),
    ].filter(Boolean),
    tracesSampleRate,
    replaysSessionSampleRate,
    replaysOnErrorSampleRate,
    ignoreErrors: [/ResizeObserver loop limit exceeded/i],
  });
}

export const SentryErrorBoundary = Sentry.ErrorBoundary;
export const captureException = Sentry.captureException;

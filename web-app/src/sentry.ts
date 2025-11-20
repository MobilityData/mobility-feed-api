import * as Sentry from '@sentry/react';
import packageJson from '../package.json';
import * as React from 'react';
import {
  createRoutesFromChildren,
  matchRoutes,
  useLocation,
  useNavigationType,
} from 'react-router-dom';

// Helper to safely parse Sentry sample rates from environment variables
const parseSampleRate = (
  value: string | undefined,
  defaultValue: number,
): number => {
  const parsed = parseFloat(value ?? String(defaultValue));
  if (isNaN(parsed) || parsed < 0 || parsed > 1) {
    return defaultValue;
  }
  return parsed;
};

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
  process.env.REACT_APP_FIREBASE_PROJECT_ID ||
  process.env.NODE_ENV ||
  'mobility-feeds-dev';
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
  const routerTracingIntegration =
    Sentry.reactRouterV6BrowserTracingIntegration({
      useEffect: React.useEffect,
      useLocation,
      useNavigationType,
      createRoutesFromChildren,
      matchRoutes,
    });

  const integrations = [];
  if (routerTracingIntegration) {
    integrations.push(routerTracingIntegration);
  }
  const replayIntegration = Sentry.replayIntegration?.();
  if (replayIntegration) {
    integrations.push(replayIntegration);
  }

  Sentry.init({
    dsn,
    environment,
    release,
    integrations: integrations,
    tracesSampleRate,
    replaysSessionSampleRate,
    replaysOnErrorSampleRate,
    ignoreErrors: [/ResizeObserver loop limit exceeded/i],
    beforeSend(event) {
      // remove user IP and geo context
      if (event.user) {
        delete event.user.ip_address;
      }
      if (event.contexts && event.contexts.geo) {
        delete event.contexts.geo;
      }
      return event;
    }
  });
}

export const SentryErrorBoundary = Sentry.ErrorBoundary;
export const captureException = Sentry.captureException;

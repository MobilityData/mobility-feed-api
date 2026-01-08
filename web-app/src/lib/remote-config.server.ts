import 'server-only';

import { cache } from 'react';
import {
  getRemoteConfig,
  type RemoteConfigParameter,
} from 'firebase-admin/remote-config';
import { getFirebaseAdminApp } from './firebase-admin';
import {
  defaultRemoteConfigValues,
  type RemoteConfigValues,
} from '../app/interface/RemoteConfig';

/**
 * Cache duration for Remote Config fetches (in seconds).
 * - Development: 5 minutes (300 seconds)
 * - Production: 1 hour (3600 seconds)
 */
const CACHE_DURATION_SECONDS =
  process.env.NODE_ENV === 'development' ? 300 : 3600;

/**
 * In-memory cache for Remote Config values.
 * This provides fast access on subsequent requests within the same server instance.
 */
let cachedConfig: RemoteConfigValues | null = null;
let cacheTimestamp: number = 0;

/**
 * Parse a Remote Config parameter value into the appropriate type.
 */
function parseConfigValue(
  value: string,
  defaultValue: boolean | number | string,
): boolean | number | string {
  const valueLower = value.toLowerCase();

  // Boolean
  if (valueLower === 'true' || valueLower === 'false') {
    return valueLower === 'true';
  }

  // Number
  if (!isNaN(Number(value)) && value.trim() !== '') {
    return Number(value);
  }

  // Default to string
  return value;
}

/**
 * Fetch Remote Config from Firebase Admin SDK.
 * Returns the template parameters merged with defaults.
 */
async function fetchRemoteConfigFromFirebase(): Promise<RemoteConfigValues> {
  const app = getFirebaseAdminApp();
  const remoteConfigAdmin = getRemoteConfig(app);

  try {
    const template = await remoteConfigAdmin.getTemplate();
    const fetchedConfig = { ...defaultRemoteConfigValues };

    // Process each parameter from the template
    for (const [key, parameter] of Object.entries(template.parameters) as [string, RemoteConfigParameter][]) {
      if (key in defaultRemoteConfigValues && parameter.defaultValue) {
        const defaultVal = parameter.defaultValue as { value?: string };
        if (defaultVal.value !== undefined) {
          const parsedValue = parseConfigValue(
            defaultVal.value,
            defaultRemoteConfigValues[key as keyof RemoteConfigValues],
          );
          (fetchedConfig as Record<string, unknown>)[key] = parsedValue;
        }
      }
    }

    return fetchedConfig;
  } catch (error) {
    console.error('Failed to fetch Remote Config from Firebase:', error);
    // Return defaults on error
    return defaultRemoteConfigValues;
  }
}

/**
 * Get Remote Config values with server-side caching.
 * This function is safe to call from Server Components and Server Actions.
 *
 * Caching strategy:
 * - React cache() deduplicates calls within the same request (e.g., layout + page)
 * - In-memory cache for fast access across multiple requests within the same server instance
 * - Cache invalidates after CACHE_DURATION_SECONDS
 * - On error, returns cached values if available, otherwise defaults
 */
export const getRemoteConfigValues = cache(
  async (): Promise<RemoteConfigValues> => {
    const now = Date.now();
    const cacheAge = (now - cacheTimestamp) / 1000;

    // Return cached config if still valid
    if (cachedConfig && cacheAge < CACHE_DURATION_SECONDS) {
      return cachedConfig;
    }

    try {
      const freshConfig = await fetchRemoteConfigFromFirebase();
      cachedConfig = freshConfig;
      cacheTimestamp = now;
      return freshConfig;
    } catch (error) {
      console.error('Error fetching Remote Config:', error);
      // Return stale cache if available, otherwise defaults
      return cachedConfig ?? defaultRemoteConfigValues;
    }
  },
);

/**
 * Force refresh the Remote Config cache.
 * Useful for admin operations or webhooks that need immediate updates.
 */
export async function refreshRemoteConfig(): Promise<RemoteConfigValues> {
  cachedConfig = null;
  cacheTimestamp = 0;
  return getRemoteConfigValues();
}

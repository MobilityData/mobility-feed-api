import { type JSONValue } from '../errorDetailsUtils';

// When loading GBFS context files for error details, cache them in localStorage
// to avoid repeated network requests. Cache entries expire after CACHE_TTL_MS.
// to avoid overflowing localStorage quota, we also provide the clearExpiredCaches()

const CACHE_TTL_MS = 10 * 60 * 1000;
const CACHE_PREFIX = 'gbfs-context:';

const getCacheKey = (url: string): string => `${CACHE_PREFIX}${url}`;

export const getCachedJson = (url: string): JSONValue | null => {
  try {
    const raw = localStorage.getItem(getCacheKey(url));
    if (raw == null) return null;
    const parsed = JSON.parse(raw) as { data: JSONValue; ts: number };
    if (
      typeof parsed.ts !== 'number' ||
      Date.now() - parsed.ts > CACHE_TTL_MS
    ) {
      localStorage.removeItem(getCacheKey(url));
      return null;
    }
    return parsed.data ?? null;
  } catch {
    return null;
  }
};

export const clearExpiredCaches = (): void => {
  try {
    const now = Date.now();
    // First collect relevant keys to avoid skipping items when localStorage changes
    const candidateKeys: string[] = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key != null && key.startsWith(CACHE_PREFIX)) candidateKeys.push(key);
    }

    const keysToRemove: string[] = [];
    for (const key of candidateKeys) {
      const raw = localStorage.getItem(key);
      if (raw == null) {
        keysToRemove.push(key);
        continue;
      }
      try {
        const parsed = JSON.parse(raw) as { ts?: number };
        if (typeof parsed.ts !== 'number' || now - parsed.ts > CACHE_TTL_MS) {
          keysToRemove.push(key);
        }
      } catch {
        // corrupted JSON — remove it
        keysToRemove.push(key);
      }
    }

    for (const k of keysToRemove) localStorage.removeItem(k);
  } catch {
    // no-op: localStorage may fail (quota, private mode, etc.)
  }
};

export const setCachedJson = (url: string, data: JSONValue): void => {
  try {
    localStorage.setItem(
      getCacheKey(url),
      JSON.stringify({
        data,
        ts: Date.now(),
      }),
    );
  } catch {
    // no-op: localStorage may fail (quota, private mode, etc.)
  }
};

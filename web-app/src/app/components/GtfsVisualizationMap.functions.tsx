'use client';

import {
  type GBFSFeedType,
  type GBFSVersionType,
} from '../services/feeds/utils';
import { type RouteIdsInput } from '../utils/precompute';
import {
  type ExpressionSpecification,
  type LngLatBoundsLike,
} from 'maplibre-gl';
import { type LatLngTuple } from 'leaflet';

export interface LatestDatasetLite {
  hosted_url?: string;
  id?: string;
  stable_id?: string;
}

// Extract route_ids list from the PMTiles property (stringified JSON)
export function extractRouteIds(val: RouteIdsInput): string[] {
  if (Array.isArray(val)) return val.map(String);
  if (typeof val === 'string') {
    try {
      const parsed = JSON.parse(val);
      if (Array.isArray(parsed)) return parsed.map(String);
    } catch {}
    // fallback: pull "quoted" tokens
    const out: string[] = [];
    val.replace(/"([^"]+)"/g, (_: unknown, id: string) => {
      out.push(id);
      return '';
    });
    if (out.length > 0) return out;
    // fallback2: CSV-ish
    return val
      .split(',')
      .map((s: string) => s.trim())
      .filter(Boolean);
  }
  return [];
}

export function generateStopColorExpression(
  routeIdToColor: Record<string, string>,
  fallback: string = '#888',
): string | ExpressionSpecification {
  const expression: Array<string | ExpressionSpecification> = [];

  const isHex = (s: string): boolean =>
    /^[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$/.test(s);

  for (const [routeId, raw] of Object.entries(routeIdToColor)) {
    if (raw == null) continue;
    const hex = String(raw).trim().replace(/^#/, '');
    if (!isHex(hex)) continue; // skip empty/invalid colors

    // route_ids is a string of quoted ids; keep your quoted match style
    expression.push(['in', `"${routeId}"`, ['get', 'route_ids']], `#${hex}`);
  }

  // If nothing valid was added, just use the fallback color directly
  if (expression.length === 0) {
    return fallback;
  }

  expression.push(fallback);
  return ['case', ...expression] as ExpressionSpecification;
}

export const getBoundsFromCoordinates = (
  coordinates: LatLngTuple[],
): LngLatBoundsLike => {
  let minLng = Number.POSITIVE_INFINITY;
  let minLat = Number.POSITIVE_INFINITY;
  let maxLng = Number.NEGATIVE_INFINITY;
  let maxLat = Number.NEGATIVE_INFINITY;

  coordinates.forEach(([lat, lng]) => {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLng = Math.min(minLng, lng);
    maxLng = Math.max(maxLng, lng);
  });

  return [minLng, minLat, maxLng, maxLat];
};

export const generatePmtilesUrls = (
  latestDataset: LatestDatasetLite | undefined,
  visualizationId: string,
): {
  stopsPmtilesUrl: string;
  routesPmtilesUrl: string;
} => {
  const baseUrl =
    latestDataset?.hosted_url != null
      ? latestDataset.hosted_url.replace(/[^/]+$/, '')
      : undefined;
  const updatedUrl = baseUrl
    ?.replace(/[^/]+$/, '')
    .replace(/\/[^/]+\/?$/, `/${visualizationId}/`);
  const stopsPmtilesUrl = `${updatedUrl ?? ''}pmtiles/stops.pmtiles`;
  const routesPmtilesUrl = `${updatedUrl ?? ''}pmtiles/routes.pmtiles`;
  return { stopsPmtilesUrl, routesPmtilesUrl };
};

export const getLatestGbfsVersion = (
  gbfsFeed: GBFSFeedType,
): GBFSVersionType | undefined => {
  const autodiscoveryVersion = gbfsFeed?.versions?.find(
    (v) => v.source === 'autodiscovery',
  );
  if (autodiscoveryVersion !== undefined) {
    return autodiscoveryVersion;
  }
  // Otherwise sort by version number and return the latest
  const sortedVersions = gbfsFeed?.versions
    ?.filter((v) => v.version !== undefined)
    .sort((a, b) => {
      if (a.version === undefined) return -1;
      if (b.version === undefined) return 1;
      if (a.version < b.version) return 1;
      if (a.version > b.version) return -1;
      return 0;
    });
  if (sortedVersions !== undefined && sortedVersions.length > 0) {
    return sortedVersions[0];
  }
  return undefined;
};

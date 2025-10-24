import { type RouteIdsInput } from '../utils/precompute';
import {
  type ExpressionSpecification,
  type LngLatBoundsLike,
} from 'maplibre-gl';

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
  fallback = '#888',
): ExpressionSpecification {
  const expression: any[] = ['case'];

  const isHex = (s: string) => /^[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$/.test(s);

  for (const [routeId, raw] of Object.entries(routeIdToColor)) {
    if (raw == null) continue;
    const hex = String(raw).trim().replace(/^#/, '');
    if (!isHex(hex)) continue; // skip empty/invalid colors

    // route_ids is a string of quoted ids; keep your quoted match style
    expression.push(['in', `"${routeId}"`, ['get', 'route_ids']], `#${hex}`);
  }

  // If nothing valid was added, just use the fallback color directly
  if (expression.length === 1) {
    return fallback as unknown as ExpressionSpecification;
  }

  expression.push(fallback);
  return expression as ExpressionSpecification;
}


export const getBoundsFromCoordinates = (
  coordinates: Array<[number, number]>,
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

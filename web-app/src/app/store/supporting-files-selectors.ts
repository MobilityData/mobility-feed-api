import { createSelector } from '@reduxjs/toolkit';
import { type GtfsRoute, type GeoJSONData } from '../types';
import { type RootState } from './store';

/**
 * Selector to retrieve the GTFS geolocation GeoJSON data from the Redux store.
 *
 * @param state - The root Redux state.
 * @returns The GeoJSONData object if available and valid, otherwise undefined.
 */
export const selectGtfsGeolocationGeojson = (
  state: RootState,
): GeoJSONData | undefined => {
  const gtfsGeolocationGeojson = state.supportingFiles.gtfsGeolocationGeojson;
  const data = state.supportingFiles.gtfsGeolocationGeojson.data;
  if (
    gtfsGeolocationGeojson != undefined &&
    gtfsGeolocationGeojson.key == 'gtfsDatasetRoutesJson'
  ) {
    return data as GeoJSONData;
  }
  return undefined;
};

/**
 * Selector to retrieve the GTFS dataset routes JSON from the Redux store.
 *
 * @param state - The root Redux state.
 * @returns An array of GtfsRoute objects if available and valid, otherwise undefined.
 */
export const selectGtfsDatasetRoutesJson = (
  state: RootState,
): GtfsRoute[] | undefined => {
  const gtfsDatasetRoutesJson = state.supportingFiles.gtfsDatasetRoutesJson;
  const data = state.supportingFiles.gtfsDatasetRoutesJson.data;
  if (
    gtfsDatasetRoutesJson != undefined &&
    gtfsDatasetRoutesJson.key == 'gtfsDatasetRoutesJson'
  ) {
    return data as GtfsRoute[];
  }
  return undefined;
};

/**
 * Selector to compute the total number of rows in the GTFS dataset routes JSON.
 *
 * @param selectGtfsDatasetRoutesJson - An array of GtfsRoute objects if available and valid, or undefined.
 * @returns The total number of rows as a number, or undefined if not available.
 */
export const selectGtfsDatasetRoutesTotal = createSelector(
  [selectGtfsDatasetRoutesJson],
  (gtfsDatasetRoutesJson: GtfsRoute[] | undefined): number | undefined => {
    if (gtfsDatasetRoutesJson == undefined) {
      return undefined;
    }
    return gtfsDatasetRoutesJson.length;
  },
);

function isValidNumber(str: string): boolean {
  if (typeof str !== 'string') return false;
  const trimmed = str.trim();
  return trimmed !== '' && Number.isFinite(Number(trimmed));
}

/**
 * Selector that derives the unique list of GTFS route types from the stored GTFS dataset routes JSON.
 *
 * This selector:
 * - Reads the GTFS routes array from the Redux store (via selectGtfsDatasetRoutesJson).
 * - Normalizes each routeType by converting to a trimmed string and ignoring null/undefined/empty values.
 * - Deduplicates routeType values.
 * - Sorts the resulting unique values with numeric-aware ordering:
 *   - If both values are numeric strings, they are compared by numeric value.
 *   - Numeric strings are ordered before non-numeric strings.
 *   - Non-numeric strings are compared lexicographically (localeCompare).
 *
 * @param state - The root Redux state.
 * @returns An array of unique, sorted route-type strings (e.g. ["0", "1", "bus", "tram"]), or `undefined` if the GTFS dataset routes JSON is not available.
 */
export const selectGtfsDatasetRouteTypes = createSelector(
  [selectGtfsDatasetRoutesJson],
  (gtfsDatasetRoutesJson: GtfsRoute[] | undefined): string[] | undefined => {
    if (gtfsDatasetRoutesJson == undefined) {
      return undefined;
    }
    const uniqueRouteTypesSet = new Set<string>();
    for (const route of gtfsDatasetRoutesJson) {
      const raw = route.routeType;
      const routeTypeStr = raw == null ? undefined : String(raw).trim();
      if (routeTypeStr != undefined) {
        uniqueRouteTypesSet.add(routeTypeStr);
      }
    }
    const uniqueRouteTypes = Array.from(uniqueRouteTypesSet);
    return uniqueRouteTypes.sort((a, b) => {
      const validNumberA = isValidNumber(a);
      const validNumberB = isValidNumber(b);
      // if both are not numbers, sort as string
      if (!validNumberA && !validNumberB) {
        return a.localeCompare(b);
      }
      // If one is not a number, number should be first
      if (!validNumberA || !validNumberB) {
        return validNumberA ? -1 : 1;
      }
      // if both are numbers then, apply number sorting
      return Number(a) - Number(b);
    });
  },
);

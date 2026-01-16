import { Box, Typography } from '@mui/material';

import { type GBFSVersionType } from '../../services/feeds/utils';
import { type LatLngTuple } from 'leaflet';

export function formatProvidersSorted(provider: string): string[] {
  const providers = provider.split(',').filter((n) => n);
  const providersTrimmed = providers.map((p) => p.trim());
  const providersSorted = providersTrimmed.sort();
  return providersSorted;
}

export function getFeedFormattedName(
  sortedProviders: string[],
  feedName?: string,
): string {
  let formattedName = '';
  if (sortedProviders[0] !== undefined && sortedProviders[0] !== '') {
    formattedName += sortedProviders[0];
  }
  if (feedName !== undefined && feedName !== '') {
    if (formattedName !== '') {
      formattedName += ', ';
    }
    formattedName += `${feedName}`;
  }
  return formattedName;
}

export function generateDescriptionMetaTag(
  t: any,
  sortedProviders: string[],
  dataType: 'gtfs' | 'gtfs_rt' | 'gbfs' | undefined,
  feedName?: string,
): string {
  const formattedName = getFeedFormattedName(sortedProviders, feedName);
  if (
    sortedProviders.length === 0 &&
    (feedName === undefined || feedName === '')
  ) {
    return '';
  }
  let dataTypeVerbose = '';
  if (dataType === 'gtfs') {
    dataTypeVerbose = t('common.gtfsSchedule');
  } else if (dataType === 'gtfs_rt') {
    dataTypeVerbose = t('common.gtfsRealtime');
  } else if (dataType === 'gbfs') {
    dataTypeVerbose = t('common.gbfs');
  }
  return t('feeds.detailPageDescription', { formattedName, dataTypeVerbose });
}

export function generatePageTitle(
  sortedProviders: string[],
  dataType: 'gtfs' | 'gtfs_rt' | 'gbfs' | undefined,
  feedName?: string,
): string {
  let newDocTitle = getFeedFormattedName(sortedProviders, feedName);

  if (newDocTitle !== '') {
    if (dataType === 'gtfs') {
      newDocTitle += ' GTFS Schedule Feed - ';
    } else if (dataType === 'gtfs_rt') {
      newDocTitle += ' GTFS Realtime Feed - ';
    } else if (dataType === 'gbfs') {
      newDocTitle += ' GBFS Feed - ';
    }
  }

  newDocTitle += 'Mobility Database';
  return newDocTitle;
}

export const formatServiceDateRange = (
  dateStart: string,
  dateEnd: string,
  timeZone?: string,
): JSX.Element => {
  const startDate = new Date(dateStart);
  const endDate = new Date(dateEnd);
  const usedTimezone = timeZone ?? 'UTC';
  // Note: If the timezone isn't set, it will default to UTC
  // If the timezone is set, but has an invalid value, it will default to the user's local timezone
  const formattedDateStart = new Intl.DateTimeFormat('en-US', {
    timeZone: usedTimezone,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(startDate);
  const formattedDateEnd = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(endDate);
  return (
    <Box>
      <Typography variant='body1'>
        {formattedDateStart}{' '}
        <Typography component={'span'} sx={{ mx: 1, fontSize: '14px' }}>
          -
        </Typography>{' '}
        {formattedDateEnd}
      </Typography>
    </Box>
  );
};

export const sortGbfsVersions = (
  a: GBFSVersionType,
  b: GBFSVersionType,
): number => {
  const na = parseFloat(String(a.version ?? '0').replace(/[^0-9.]/g, ''));
  const nb = parseFloat(String(b.version ?? '0').replace(/[^0-9.]/g, ''));

  if (Number.isNaN(na) || Number.isNaN(nb)) {
    return -1;
  }

  if (na !== nb) {
    return nb - na;
  }

  if (a.source === b.source) return 0;
  return a.source === 'autodiscovery' ? -1 : 1;
};

// Could be temporary function
// Discuss if gbfs-feeds endpoint should include the bounding box
/* eslint-disable */
export function computeBoundingBox(
  geojson: any,
): LatLngTuple[] | undefined {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;

  function extend(coord: any) {
    const [x, y] = coord;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }

  function extractCoords(geometry: any) {
    if (!geometry) return undefined;
    const { type, coordinates } = geometry;

    if (type === 'Point') {
      extend(coordinates);
    } else if (type === 'MultiPoint' || type === 'LineString') {
      coordinates.forEach(extend);
    } else if (type === 'MultiLineString' || type === 'Polygon') {
      coordinates.forEach((line: any) => line.forEach(extend));
    } else if (type === 'MultiPolygon') {
      coordinates.forEach((polygon: any) =>
        polygon.forEach((line: any) => line.forEach(extend)),
      );
    } else if (type === 'GeometryCollection') {
      geometry.geometries.forEach(extractCoords);
    }
  }

  if (geojson.type === 'FeatureCollection') {
    geojson.features.forEach((f: any) => extractCoords(f.geometry));
  }

  if (
    minX === Infinity ||
    minY === Infinity ||
    maxX === -Infinity ||
    maxY === -Infinity
  ) {
    return undefined;
  }

  return [
    [minY, minX],
    [maxY, maxX],
  ];
}

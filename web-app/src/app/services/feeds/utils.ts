import { getEmojiFlag, type TCountryCode } from 'countries-list';
import { type paths, type components } from './types';

export type AllFeedsType =
  paths['/v1/search']['get']['responses'][200]['content']['application/json'];

export type EntityLocations = components['schemas']['Locations'];

export type AllFeedsParams = paths['/v1/search']['get']['parameters'];

export type AllFeedType =
  | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
  | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export type BasicFeedType =
  | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export const isBasicFeedType = (
  data: AllFeedType,
): data is paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json'] => {
  return data !== undefined;
};

export type GTFSFeedType =
  | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export const isGtfsFeedType = (
  data: AllFeedType,
): data is paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json'] => {
  return data !== undefined && data.data_type === 'gtfs';
};

export type GTFSRTFeedType =
  | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export const isGtfsRtFeedType = (
  data: AllFeedType,
): data is paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json'] => {
  return data !== undefined && data.data_type === 'gtfs_rt';
};

export type AllDatasetType =
  | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
  | paths['/v1/datasets/gtfs/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export function getLocationName(
  locations: EntityLocations | undefined | null,
): string {
  if (locations === undefined || locations === null) {
    return '';
  }
  let displayLocation = '';
  locations.forEach((location, index) => {
    if (location.country_code !== undefined && location.country_code !== null) {
      displayLocation += `${getEmojiFlag(
        location.country_code as TCountryCode,
      )} `;
    }
    if (location.country !== undefined && location.country !== null) {
      displayLocation += `${location.country}`;
    }
    if (
      location.subdivision_name !== undefined &&
      location.subdivision_name !== null
    ) {
      displayLocation += `, ${location.subdivision_name}`;
    }
    if (location.municipality !== undefined && location.municipality !== null) {
      displayLocation += `, ${location.municipality}`;
    }

    if (index < locations.length - 1) {
      displayLocation += ' | ';
    }
  });
  return displayLocation;
}

export function isValidFeedLink(feedLink: string): boolean {
  const lowercaseFeedLink = feedLink.toLowerCase();
  const urlPattern = /^(https?:\/\/)([^\s$.?#].[^\s]*)$/;
  return urlPattern.test(lowercaseFeedLink ?? '');
}

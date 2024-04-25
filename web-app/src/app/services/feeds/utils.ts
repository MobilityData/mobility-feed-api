import { type paths } from './types';

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

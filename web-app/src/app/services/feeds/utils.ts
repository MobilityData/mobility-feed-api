import { type paths } from '../feeds/types';

export type AllFeedType =
  | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
  | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export type GTFSFeedType =
  | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined;

export const isGtfsFeedType = (
  data: AllFeedType,
): data is paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json'] => {
  return data !== undefined && data.data_type === 'gtfs';
};

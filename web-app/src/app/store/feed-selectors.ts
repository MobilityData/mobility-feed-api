import { type paths } from '../services/feeds/types';
import { type GTFSFeedType, isGtfsFeedType } from '../services/feeds/utils';
import { type RootState } from './store';

export const selectFeedData = (
  state: RootState,
):
  | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined => {
  return state.feedProfile.data;
};
export const selectGTFSFeedData = (state: RootState): GTFSFeedType => {
  return isGtfsFeedType(state.feedProfile.data)
    ? state.feedProfile.data
    : undefined;
};

export const selectFeedId = (state: RootState): string => {
  return state.feedProfile.feedId ?? 'mdb-1';
};

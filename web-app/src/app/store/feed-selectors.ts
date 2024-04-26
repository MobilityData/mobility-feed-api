import {
  type GTFSFeedType,
  isGtfsFeedType,
  type BasicFeedType,
} from '../services/feeds/utils';
import { type RootState } from './store';

export const selectFeedData = (state: RootState): BasicFeedType => {
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

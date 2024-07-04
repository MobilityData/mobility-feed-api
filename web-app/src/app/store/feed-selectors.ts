import {
  type GTFSFeedType,
  type GTFSRTFeedType,
  isGtfsFeedType,
  isGtfsRtFeedType,
  type BasicFeedType,
  type AllFeedType,
} from '../services/feeds/utils';
import { type RootState } from './store';

export const selectFeedData = (state: RootState): BasicFeedType => {
  return state.feedProfile.data;
};

export const selectFeedLoadingStatus = (state: RootState): string => {
  return state.feedProfile.status;
};
export const selectGTFSFeedData = (state: RootState): GTFSFeedType => {
  return isGtfsFeedType(state.feedProfile.data)
    ? state.feedProfile.data
    : undefined;
};
export const selectGTFSRTFeedData = (state: RootState): GTFSRTFeedType => {
  return isGtfsRtFeedType(state.feedProfile.data)
    ? state.feedProfile.data
    : undefined;
};

export const selectFeedId = (state: RootState): string => {
  return state.feedProfile.feedId ?? 'mdb-1';
};

export const selectRelatedFeedsData = (state: RootState): AllFeedType[] => {
  return state.feedProfile.relatedFeedsData;
};

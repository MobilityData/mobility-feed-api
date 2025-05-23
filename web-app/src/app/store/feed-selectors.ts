import {
  type GTFSFeedType,
  type GTFSRTFeedType,
  isGtfsFeedType,
  isGtfsRtFeedType,
  type BasicFeedType,
  type AllFeedType,
  type GBFSFeedType,
  isGbfsFeedType,
  type GBFSVersionType,
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
export const selectGBFSFeedData = (state: RootState): GBFSFeedType => {
  return isGbfsFeedType(state.feedProfile.data)
    ? state.feedProfile.data
    : undefined;
};

export const selectFeedId = (state: RootState): string => {
  return state.feedProfile.feedId ?? 'mdb-1';
};

export const selectLatestGbfsVersion = (
  state: RootState,
): GBFSVersionType | undefined => {
  if (state.feedProfile.data?.data_type === 'gbfs') {
    const latestGbfsVersion = (
      state.feedProfile.data as GBFSFeedType
    )?.versions?.find((v) => v.latest);
    return latestGbfsVersion;
  }
  return undefined;
};

export const selectRelatedFeedsData = (state: RootState): AllFeedType[] => {
  return state.feedProfile.relatedFeedsData.gtfs;
};
export const selectRelatedGtfsRTFeedsData = (
  state: RootState,
): GTFSRTFeedType[] => {
  return state.feedProfile.relatedFeedsData.gtfsRt;
};

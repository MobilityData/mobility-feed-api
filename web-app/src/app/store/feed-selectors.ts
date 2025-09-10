import {
  type AllFeedType,
  type BasicFeedType,
  type GBFSFeedType,
  type GBFSVersionType,
  type GTFSFeedType,
  type GTFSRTFeedType,
  isGbfsFeedType,
  isGtfsFeedType,
  isGtfsRtFeedType,
} from '../services/feeds/utils';
import { type RootState } from './store';
import type { LatLngExpression } from 'leaflet';

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

export const selectAutodiscoveryGbfsVersion = (
  state: RootState,
): GBFSVersionType | undefined => {
  if (state.feedProfile.data?.data_type === 'gbfs') {
    return (state.feedProfile.data as GBFSFeedType)?.versions?.find(
      (v) => v.source === 'autodiscovery',
    );
  }
  return undefined;
};

export const selectAutoDiscoveryUrl = (
  state: RootState,
): string | undefined => {
  if (state.feedProfile.data?.data_type === 'gbfs') {
    const gbfsFeed: GBFSFeedType = state.feedProfile.data;
    return (
      gbfsFeed?.versions
        ?.find((v) => v.source === 'autodiscovery')
        ?.endpoints?.find((e) => e.name === 'gbfs')?.url ??
      gbfsFeed?.source_info?.producer_url
    );
  }
};

export const selectRelatedFeedsData = (state: RootState): AllFeedType[] => {
  return state.feedProfile.relatedFeedsData.gtfs;
};
export const selectRelatedGtfsRTFeedsData = (
  state: RootState,
): GTFSRTFeedType[] => {
  return state.feedProfile.relatedFeedsData.gtfsRt;
};

export const selectGtfsFeedBoundingBox = (
  state: RootState,
): LatLngExpression[] | undefined => {
  if (!isGtfsFeedType(state.feedProfile.data)) {
    return undefined;
  }
  const feed = state.feedProfile.data as GTFSFeedType;

  if (
    feed?.bounding_box?.maximum_latitude == undefined ||
    feed?.bounding_box.maximum_longitude == undefined ||
    feed?.bounding_box.minimum_latitude == undefined ||
    feed?.bounding_box.minimum_longitude == undefined
  ) {
    return undefined;
  }
  return [
    [feed.bounding_box.minimum_latitude, feed.bounding_box.minimum_longitude],
    [feed.bounding_box.minimum_latitude, feed.bounding_box.maximum_longitude],
    [feed.bounding_box.maximum_latitude, feed.bounding_box.maximum_longitude],
    [feed.bounding_box.maximum_latitude, feed.bounding_box.minimum_longitude],
  ];
};

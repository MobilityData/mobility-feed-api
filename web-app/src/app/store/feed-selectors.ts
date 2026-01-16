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
import type { LatLngTuple } from 'leaflet';

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
    const autodiscoveryVersion = (
      state.feedProfile.data as GBFSFeedType
    )?.versions?.find((v) => v.source === 'autodiscovery');
    if (autodiscoveryVersion !== undefined) {
      return autodiscoveryVersion;
    }
    const gbfsFeed: GBFSFeedType = state.feedProfile.data;
    const sortedVersions = gbfsFeed?.versions
      ?.filter((v) => v.version !== undefined)
      .sort((a, b) => {
        if (a.version === undefined) return -1;
        if (b.version === undefined) return 1;
        if (a.version < b.version) return 1;
        if (a.version > b.version) return -1;
        return 0;
      });
    if (sortedVersions !== undefined && sortedVersions.length > 0) {
      return sortedVersions[0];
    }
  }
  return undefined;
};

export const selectLatestGtfsDatasetId = (
  state: RootState,
): string | undefined => {
  if (state.feedProfile.data?.data_type === 'gtfs') {
    const gtfsFeed: GTFSFeedType = state.feedProfile.data;
    return gtfsFeed?.latest_dataset?.id ?? undefined;
  }
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

export const selectFeedBoundingBox = (
  state: RootState,
): LatLngTuple[] | undefined => {
  if (
    !(
      isGtfsFeedType(state.feedProfile.data) ||
      isGbfsFeedType(state.feedProfile.data)
    )
  ) {
    return undefined;
  }
  const feed = state.feedProfile.data;

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

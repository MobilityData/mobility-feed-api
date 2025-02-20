import {
  type StrictEffect,
  all,
  call,
  takeLatest,
  put,
} from 'redux-saga/effects';
import {
  loadingFeedFail,
  loadingFeedSuccess,
  loadingRelatedFeedsFail,
  loadingRelatedFeedsSuccess,
} from '../feed-reducer';
import { getAppError } from '../../utils/error';
import {
  FEED_PROFILE_LOADING_FEED,
  FEED_PROFILE_LOADING_RELATED_FEEDS,
  type FeedError,
} from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import {
  getFeed,
  getGtfsFeed,
  getGtfsFeedAssociatedGtfsRtFeeds,
  getGtfsRtFeed,
} from '../../services/feeds';
import {
  type GTFSRTFeedType,
  type AllFeedType,
} from '../../services/feeds/utils';
import { getUserAccessToken } from '../../services';

function* getFeedSaga({
  payload: { feedId, feedDataType },
}: PayloadAction<{ feedId: string; feedDataType?: string }>): Generator<
  StrictEffect,
  void,
  AllFeedType
> {
  try {
    if (feedId !== undefined) {
      const accessToken = (yield call(getUserAccessToken)) as string;
      let isGtfs = false;
      if (feedDataType == undefined) {
        const basicFeed = yield call(getFeed, feedId, accessToken);
        isGtfs = basicFeed?.data_type === 'gtfs';
      } else {
        isGtfs = feedDataType === 'gtfs';
      }
      const feed = isGtfs
        ? yield call(getGtfsFeed, feedId, accessToken)
        : yield call(getGtfsRtFeed, feedId, accessToken);
      yield put(loadingFeedSuccess({ data: feed }));
    }
  } catch (error) {
    yield put(loadingFeedFail(getAppError(error) as FeedError));
  }
}

function* getRelatedFeedsSaga({
  payload: { feedIds },
}: PayloadAction<{ feedIds: string[] }>): Generator {
  try {
    if (feedIds.length > 0) {
      const accessToken = (yield call(getUserAccessToken)) as string;
      const feedsData: AllFeedType[] = (yield all(
        feedIds.map((feedId) =>
          call(
            function* (
              feedId: string,
              accessToken: string,
            ): Generator<StrictEffect, AllFeedType, AllFeedType> {
              const feed = yield call(getGtfsFeed, feedId, accessToken);
              return feed;
            },
            feedId,
            accessToken,
          ),
        ),
      )) as AllFeedType[];

      const gtfsRtFeedsData = (yield all(
        feedIds.map((feedId) =>
          call(getGtfsFeedAssociatedGtfsRtFeeds, feedId, accessToken),
        ),
      )) as GTFSRTFeedType[];
      const flattenedGtfsRtFeedsData = gtfsRtFeedsData.flat();
      const uniqueGtfsRtFeedsData: GTFSRTFeedType[] = [];
      const uniqueFeedRtIds = new Set();
      flattenedGtfsRtFeedsData.forEach((feed) => {
        if (uniqueFeedRtIds.has(feed?.id)) return;
        uniqueGtfsRtFeedsData.push(feed);
        uniqueFeedRtIds.add(feed?.id);
      });
      yield put(
        loadingRelatedFeedsSuccess({
          data: {
            gtfs: feedsData,
            gtfsRt: uniqueGtfsRtFeedsData,
          },
        }),
      );
    }
  } catch (error) {
    yield put(loadingRelatedFeedsFail(getAppError(error) as FeedError));
  }
}

export function* watchFeed(): Generator {
  yield takeLatest(FEED_PROFILE_LOADING_FEED, getFeedSaga);
  yield takeLatest(FEED_PROFILE_LOADING_RELATED_FEEDS, getRelatedFeedsSaga);
}

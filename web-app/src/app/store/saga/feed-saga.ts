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
import { getFeed, getGtfsFeed, getGtfsRtFeed } from '../../services/feeds';
import { type AllFeedType } from '../../services/feeds/utils';

function* getFeedSaga({
  payload: { feedId, accessToken },
}: PayloadAction<{ feedId: string; accessToken: string }>): Generator<
  StrictEffect,
  void,
  AllFeedType
> {
  try {
    if (feedId !== undefined) {
      const basicFeed = yield call(getFeed, feedId, accessToken);
      const feed =
        basicFeed?.data_type === 'gtfs'
          ? yield call(getGtfsFeed, feedId, accessToken)
          : yield call(getGtfsRtFeed, feedId, accessToken);
      yield put(loadingFeedSuccess({ data: feed }));
    }
  } catch (error) {
    yield put(loadingFeedFail(getAppError(error) as FeedError));
  }
}

function* getRelatedFeedsSaga({
  payload: { feedIds, accessToken },
}: PayloadAction<{ feedIds: string[]; accessToken: string }>): Generator<
  StrictEffect,
  void,
  AllFeedType[]
> {
  try {
    if (feedIds.length > 0) {
      const feedsData: AllFeedType[] = yield all(
        feedIds.map((feedId) =>
          call(
            function* (
              feedId: string,
              accessToken: string,
            ): Generator<StrictEffect, AllFeedType, AllFeedType> {
              const basicFeed = yield call(getFeed, feedId, accessToken);
              const feed =
                basicFeed?.data_type === 'gtfs'
                  ? yield call(getGtfsFeed, feedId, accessToken)
                  : yield call(getGtfsRtFeed, feedId, accessToken);
              return feed;
            },
            feedId,
            accessToken,
          ),
        ),
      );
      yield put(loadingRelatedFeedsSuccess({ data: feedsData }));
    }
  } catch (error) {
    yield put(loadingRelatedFeedsFail(getAppError(error) as FeedError));
  }
}

export function* watchFeed(): Generator {
  yield takeLatest(FEED_PROFILE_LOADING_FEED, getFeedSaga);
  yield takeLatest(FEED_PROFILE_LOADING_RELATED_FEEDS, getRelatedFeedsSaga);
}

import { type StrictEffect, call, takeLatest, put } from 'redux-saga/effects';
import { loadingFeedFail, loadingFeedSuccess } from '../feed-reducer';
import { getAppError } from '../../utils/error';
import { type paths } from '../../services/feeds/types';
import { FEED_PROFILE_LOADING_FEED } from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import { getGtfsFeed } from '../../services/feeds';

function* getFeedSaga({
  payload: { feedId, accessToken },
}: PayloadAction<{ feedId: string; accessToken: string }>): Generator<
  StrictEffect,
  void,
  | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
  | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined
> {
  try {
    if (feedId !== undefined) {
      const feed = yield call(getGtfsFeed, feedId, accessToken);
      yield put(loadingFeedSuccess({ data: feed }));
    }
  } catch (error) {
    yield put(loadingFeedFail(getAppError(error)));
  }
}

export function* watchFeed(): Generator {
  yield takeLatest(FEED_PROFILE_LOADING_FEED, getFeedSaga);
  // yield takeLatest(USER_PROFILE_REFRESH_INFORMATION, refreshUserInformation);
}

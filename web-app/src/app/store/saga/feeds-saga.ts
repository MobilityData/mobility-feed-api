import { takeLatest, put, call } from 'redux-saga/effects';
import { getAppError } from '../../utils/error';
import { FEEDS_LOADING_FEEDS, type FeedError } from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import {
  type AllFeedsType,
  type AllFeedsParams,
} from '../../services/feeds/utils';
import { loadingFeedsFail, loadingFeedsSuccess } from '../feeds-reducer';
import { searchFeeds } from '../../services/feeds';
import { getUserAccessToken } from '../../services/profile-service';

function* getFeedsSaga({
  payload: { params },
}: PayloadAction<{
  params: AllFeedsParams;
  accessToken: string;
}>): Generator {
  try {
    const accessToken = (yield call(getUserAccessToken)) as string;
    const searchData: AllFeedsType = (yield call(
      searchFeeds,
      params,
      accessToken,
    )) as AllFeedsType;
    yield put(loadingFeedsSuccess({ data: searchData }));
  } catch (error) {
    yield put(loadingFeedsFail(getAppError(error) as FeedError));
  }
}

export function* watchFeeds(): Generator {
  yield takeLatest(FEEDS_LOADING_FEEDS, getFeedsSaga);
}

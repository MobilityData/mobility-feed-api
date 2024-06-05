import { type StrictEffect, call, takeLatest, put } from 'redux-saga/effects';
import { loadingFeedFail } from '../feed-reducer';
import { getAppError } from '../../utils/error';
import { DATASET_LOADING_FEED, type FeedError } from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import { getGtfsFeedDatasets } from '../../services/feeds';
import { type paths } from '../../services/feeds/types';
import { loadingDatasetSuccess } from '../dataset-reducer';

function* getDatasetSaga({
  payload: { feedId, accessToken },
}: PayloadAction<{ feedId: string; accessToken: string }>): Generator<
  StrictEffect,
  void,
  paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
> {
  try {
    if (feedId !== undefined) {
      const datasets = yield call(getGtfsFeedDatasets, feedId, accessToken, {});
      yield put(loadingDatasetSuccess({ data: datasets }));
    }
  } catch (error) {
    yield put(loadingFeedFail(getAppError(error) as FeedError));
  }
}

export function* watchDataset(): Generator {
  yield takeLatest(DATASET_LOADING_FEED, getDatasetSaga);
}

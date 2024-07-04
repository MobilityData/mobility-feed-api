import { call, takeLatest, put } from 'redux-saga/effects';
import { loadingFeedFail } from '../feed-reducer';
import { getAppError } from '../../utils/error';
import { DATASET_LOADING_FEED, type FeedError } from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import { getGtfsFeedDatasets } from '../../services/feeds';
import { type paths } from '../../services/feeds/types';
import { loadingDatasetSuccess } from '../dataset-reducer';
import { getUserAccessToken } from '../../services';

function* getDatasetSaga({
  payload: { feedId },
}: PayloadAction<{ feedId: string }>): Generator {
  try {
    if (feedId !== undefined) {
      const accessToken: string | null = (yield call(
        getUserAccessToken,
      )) as string;
      const datasets = (yield call(
        getGtfsFeedDatasets,
        feedId,
        accessToken,
        {},
      )) as paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];
      yield put(loadingDatasetSuccess({ data: datasets }));
    }
  } catch (error) {
    yield put(loadingFeedFail(getAppError(error) as FeedError));
  }
}

export function* watchDataset(): Generator {
  yield takeLatest(DATASET_LOADING_FEED, getDatasetSaga);
}

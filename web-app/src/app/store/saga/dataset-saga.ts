import { call, takeLatest, put } from 'redux-saga/effects';
import { loadingFeedFail } from '../feed-reducer';
import { getAppError } from '../../utils/error';
import { DATASET_LOADING_FEED, type FeedError } from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import { getGtfsFeedDatasets } from '../../services/feeds';
import { type paths } from '../../services/feeds/types';
import { loadingDatasetSuccess } from '../dataset-reducer';
import { getUserAccessToken } from '../../services';
import { areAllDatasetsLoaded } from '../../utils/dataset';

function* getDatasetSaga({
  payload: { feedId, offset, limit },
}: PayloadAction<{
  feedId: string;
  offset?: number;
  limit?: number;
}>): Generator {
  try {
    if (feedId !== undefined) {
      const accessToken = (yield call(getUserAccessToken)) as string;
      const datasets = (yield call(getGtfsFeedDatasets, feedId, accessToken, {
        offset,
        limit,
      })) as paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];
      const hasLoadedAllData = areAllDatasetsLoaded(
        datasets.length,
        limit,
        offset,
      );
      yield put(
        loadingDatasetSuccess({
          data: datasets,
          loadedAllData: hasLoadedAllData,
        }),
      );
    }
  } catch (error) {
    yield put(loadingFeedFail(getAppError(error) as FeedError));
  }
}

export function* watchDataset(): Generator {
  yield takeLatest(DATASET_LOADING_FEED, getDatasetSaga);
}

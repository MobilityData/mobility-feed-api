import { call, put, takeLatest, select } from 'redux-saga/effects';
import {
  loadingSupportingFile,
  loadingSupportingFileSuccess,
  loadingSupportingFileFail,
  setSupportingFilesContext,
  clearSupportingFiles,
} from '../supporting-files-reducer';
import { getAppError } from '../../utils/error';
import { getJson } from '../../services/http';
import { loadingDatasetSuccess } from '../dataset-reducer';
import { selectLatestDatasetsData } from '../dataset-selectors';
import {
  updateFeedId,
  loadingFeedSuccess,
  loadingFeedFail,
} from '../feed-reducer';
import { selectFeedData, selectLatestGtfsDatasetId } from '../feed-selectors';
import {
  type GtfsRoute,
  type GeoJSONData,
  type GeoJSONDataGBFS,
} from '../../types';
import { getFeedFilesBaseUrl } from '../../utils/config';

export function buildRoutesUrl(feedId: string, datasetId: string): string {
  return `${getFeedFilesBaseUrl()}/${feedId}/${datasetId}/pmtiles/routes.json`;
}

export function* loadSupportingFileSaga({
  payload: { key, url },
}: ReturnType<typeof loadingSupportingFile>): Generator<
  unknown,
  void,
  unknown
> {
  try {
    const data = (yield call(getJson, url)) as
      | GeoJSONData
      | GeoJSONDataGBFS
      | GtfsRoute[];
    // Dispatch success with the parsed data
    yield put(loadingSupportingFileSuccess({ key, data }));
  } catch (error) {
    const appError = getAppError(error);
    const message = appError.message;
    yield put(loadingSupportingFileFail({ key, error: message }));
  }
}

const handleFeedChangeFail = function* (): Generator<unknown, void, unknown> {
  // Clear any supporting files loaded for a previous feed.
  yield put(clearSupportingFiles());
};

const handleFeedChange = function* (): Generator<unknown, void, unknown> {
  const feed = (yield select(selectFeedData)) as
    | { id?: string; data_type?: string }
    | undefined;
  const feedId = feed?.id;
  const dataType = feed?.data_type;

  // Read previous feedId from supporting-files context so we only clear/reload
  // when the feed actually changed.
  const previousContext = (yield select((s) => s.supportingFiles)) as
    | { context?: { feedId?: string } }
    | undefined;
  const previousFeedId = previousContext?.context?.feedId;

  // If feedId hasn't changed or it's, do nothing.
  if (previousFeedId === feedId) {
    return;
  }
  // This function it's only applied to gbfs feeds. GTFS feeds are processed when dataset is loaded

  // Set the context in the supporting-files state so we can track which
  // feed the files belong to.
  yield put(setSupportingFilesContext({ feedId, dataType }));

  // Clear any supporting files loaded for a previous feed.
  yield put(clearSupportingFiles());

  if (feed?.data_type === 'gtfs') {
    const datasetId = (yield select(selectLatestGtfsDatasetId)) as
      | string
      | undefined;
    if (datasetId !== undefined && feedId !== undefined) {
      const url = buildRoutesUrl(feedId, datasetId);
      yield put(loadingSupportingFile({ key: 'gtfsDatasetRoutesJson', url }));
    }
  }
};

const handleDatasetChange = function* (): Generator<unknown, void, unknown> {
  const dataset = (yield select(selectLatestDatasetsData)) as
    | { id?: string; feed_id?: string }
    | undefined;
  const feedId = dataset?.feed_id;
  const datasetId = dataset?.id;

  // Read previous feedId from supporting-files context so we only clear/reload
  // when the feed actually changed.
  const previousContext = (yield select((s) => s.supportingFiles)) as
    | { context?: { datasetId?: string } }
    | undefined;
  const previousDatasetId = previousContext?.context?.datasetId;

  // If datasetId hasn't changed or it's, do nothing.
  if (previousDatasetId === datasetId) {
    return;
  }

  // Set the context in the supporting-files state so we can track which
  // feed the files belong to.
  yield put(setSupportingFilesContext({ feedId, dataType: 'gtfs' }));

  // Clear any supporting files loaded for a previous feed.
  yield put(clearSupportingFiles());

  if (datasetId !== undefined && feedId !== undefined) {
    const url = buildRoutesUrl(feedId, datasetId);
    yield put(loadingSupportingFile({ key: 'gtfsDatasetRoutesJson', url }));
  }
};

export function* watchSupportingFiles(): Generator {
  yield takeLatest(updateFeedId.type, handleFeedChange);
  yield takeLatest(loadingFeedSuccess.type, handleFeedChange);
  yield takeLatest(loadingFeedFail.type, handleFeedChangeFail);
  yield takeLatest(loadingDatasetSuccess.type, handleDatasetChange);
  yield takeLatest(loadingSupportingFile.type, loadSupportingFileSaga);
}

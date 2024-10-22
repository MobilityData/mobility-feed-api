import { call, put, takeLatest } from 'redux-saga/effects';
import {
  fetchDataStart,
  fetchFeedMetricsSuccess,
  fetchFeedMetricsFailure,
  fetchAvailableFilesSuccess,
  selectFile,
  fetchAvailableFilesStart,
} from '../gtfs-analytics-reducer';
import {
  type AnalyticsFile,
  type GTFSFeedMetrics,
  type GTFSMetrics,
} from '../../screens/Analytics/types';
import { getLocationName } from '../../services/feeds/utils';
import { getAnalyticsBucketEndpoint } from '../../screens/Analytics/GTFSFeedAnalytics';

function* fetchFeedMetricsSaga(
  action: ReturnType<typeof selectFile>,
): Generator<unknown, void, never> {
  try {
    const selectedFile = action.payload;

    // Fetch feed metrics
    const feedMetricsResponse: Response = yield call(
      fetch,
      `${getAnalyticsBucketEndpoint()}/${selectedFile}`,
    );
    if (!feedMetricsResponse.ok) {
      throw new Error(
        `Error ${feedMetricsResponse.status}: ${feedMetricsResponse.statusText}`,
      );
    }
    const feedMetrics: GTFSFeedMetrics[] = yield feedMetricsResponse.json();

    // Add a locations_string property to each feed
    feedMetrics.forEach((feed) => {
      feed.locations_string = getLocationName(feed.locations);
    });

    // Fetch analytics metrics
    const analyticsMetricsResponse: Response = yield call(
      fetch,
      `${getAnalyticsBucketEndpoint()}/feed_metrics.json`,
    );
    if (!analyticsMetricsResponse.ok) {
      throw new Error(
        `Error ${analyticsMetricsResponse.status}: ${analyticsMetricsResponse.statusText}`,
      );
    }
    const analyticsMetrics: GTFSMetrics[] =
      yield analyticsMetricsResponse.json();

    // Merge metrics based on feed_id
    const mergedMetrics: GTFSFeedMetrics[] = feedMetrics.map(
      (feed): GTFSFeedMetrics => {
        const analyticsMetric = analyticsMetrics.find(
          (metric) => metric.feed_id === feed.feed_id,
        );
        return {
          ...feed,
          metrics: analyticsMetric,
        };
      },
    );
    // Dispatch the merged metrics
    yield put(fetchFeedMetricsSuccess(mergedMetrics));
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    yield put(fetchFeedMetricsFailure(errorMessage));
  }
}

function* fetchAvailableFilesSaga(): Generator<unknown, void, never> {
  try {
    const response: Response = yield call(
      fetch,
      `${getAnalyticsBucketEndpoint()}/analytics_files.json`,
    );
    if (!response.ok) {
      throw new Error(`Error ${response.status}: ${response.statusText}`);
    }
    const files: AnalyticsFile[] = yield response.json();
    yield put(fetchAvailableFilesSuccess(files));
    if (files.length > 0) {
      // Select the latest file by default
      const latestFile = files[files.length - 1].file_name;
      yield put(selectFile(latestFile));
    }
  } catch (error) {
    yield put(
      fetchFeedMetricsFailure(
        error instanceof Error ? error.message : 'An unknown error occurred',
      ),
    );
  }
}

export function* watchGTFSFetchFeedMetrics(): Generator<unknown, void, never> {
  yield takeLatest(fetchDataStart.type, fetchFeedMetricsSaga);
  yield takeLatest(selectFile.type, fetchFeedMetricsSaga);
  yield takeLatest(fetchAvailableFilesStart.type, fetchAvailableFilesSaga);
}

import { call, put, takeLatest } from 'redux-saga/effects';
import {
  fetchDataStart,
  fetchFeedMetricsSuccess,
  fetchFeedMetricsFailure,
  fetchAvailableFilesSuccess,
  selectFile,
  fetchAvailableFilesStart,
} from '../gbfs-analytics-reducer';
import {
  type AnalyticsFile,
  type GBFSFeedMetrics,
  type GBFSMetrics,
} from '../../screens/Analytics/types';
import { getLocationName } from '../../services/feeds/utils';
import { getAnalyticsBucketEndpoint } from '../../screens/Analytics/GBFSFeedAnalytics';

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
    const feedMetrics: GBFSFeedMetrics[] = yield feedMetricsResponse.json();
    const analyticsMetricsResponse: Response = yield call(
      fetch,
      `${getAnalyticsBucketEndpoint()}/feed_metrics.json`,
    );
    if (!analyticsMetricsResponse.ok) {
      throw new Error(
        `Error ${analyticsMetricsResponse.status}: ${analyticsMetricsResponse.statusText}`,
      );
    }
    const analyticsMetrics: GBFSMetrics[] =
      yield analyticsMetricsResponse.json();

    // Add a locations_string property to each feed
    feedMetrics.forEach((feed) => {
      feed.locations_string = getLocationName(feed.locations);
    });

    const mergedMetrics: GBFSFeedMetrics[] = feedMetrics.map(
      (feed): GBFSFeedMetrics => {
        const analyticsMetric = analyticsMetrics.find(
          (metric) => metric.feed_id === feed.feed_id,
        );
        return {
          ...feed,
          metrics: analyticsMetric,
        };
      },
    );

    // Dispatch the feed metrics
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

export function* watchGBFSFetchFeedMetrics(): Generator<unknown, void, never> {
  yield takeLatest(fetchDataStart.type, fetchFeedMetricsSaga);
  yield takeLatest(selectFile.type, fetchFeedMetricsSaga);
  yield takeLatest(fetchAvailableFilesStart.type, fetchAvailableFilesSaga);
}

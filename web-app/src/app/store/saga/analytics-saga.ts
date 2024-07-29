import { call, put, takeLatest } from 'redux-saga/effects';
import {
  fetchDataStart,
  fetchFeedMetricsSuccess,
  fetchFeedMetricsFailure,
} from '../analytics-reducer';
import { type FeedMetrics, type Metrics } from '../../screens/Analytics/types';

function* fetchFeedMetricsSaga(): Generator<unknown, void, never> {
  try {
    console.log('fetchFeedMetricsSaga');

    // Fetch feed metrics
    const feedMetricsResponse: Response = yield call(
      fetch,
      'https://storage.googleapis.com/mobilitydata-analytics-dev/analytics_2024_07.json',
    );
    console.log('fetchFeedMetricsSaga response', feedMetricsResponse);
    if (!feedMetricsResponse.ok) {
      throw new Error(
        `Error ${feedMetricsResponse.status}: ${feedMetricsResponse.statusText}`,
      );
    }
    const feedMetrics: FeedMetrics[] = yield feedMetricsResponse.json();

    // Fetch analytics metrics
    const analyticsMetricsResponse: Response = yield call(
      fetch,
      'https://storage.googleapis.com/mobilitydata-analytics-dev/feed_metrics.json',
    );
    if (!analyticsMetricsResponse.ok) {
      throw new Error(
        `Error ${analyticsMetricsResponse.status}: ${analyticsMetricsResponse.statusText}`,
      );
    }
    const analyticsMetrics: Metrics[] = yield analyticsMetricsResponse.json();

    // Merge metrics based on feed_id
    const mergedMetrics: FeedMetrics[] = feedMetrics.map(
      (feed): FeedMetrics => {
        const analyticsMetric = analyticsMetrics.find(
          (metric) => metric.feed_id === feed.feed_id,
        );
        return {
          ...feed,
          metrics: analyticsMetric,
        };
      },
    );
    console.log('fetchFeedMetricsSaga mergedMetrics', mergedMetrics);
    // Dispatch the merged metrics
    yield put(fetchFeedMetricsSuccess(mergedMetrics));
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : 'An unknown error occurred';
    yield put(fetchFeedMetricsFailure(errorMessage));
  }
}

export function* watchFetchFeedMetrics() {
  yield takeLatest(fetchDataStart.type, fetchFeedMetricsSaga);
}

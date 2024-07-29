import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type NoticeMetrics,
  type FeatureMetrics,
  type FeedMetrics,
} from '../screens/Analytics/types';

interface AnalyticsState {
  feedMetrics: FeedMetrics[];
  historicalMetrics: Map<string, FeatureMetrics>;
  noticeMetrics: NoticeMetrics[];
  featuresMetrics: FeatureMetrics[];
  status: 'loading' | 'loaded' | 'failed';
  error?: string;
}

const initialState: AnalyticsState = {
  feedMetrics: [],
  historicalMetrics: new Map(),
  noticeMetrics: [],
  featuresMetrics: [],
  status: 'loading',
  error: undefined,
};

const AnalyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    fetchDataStart(state) {
      state.status = 'loading';
    },
    fetchFeedMetricsSuccess(state, action: PayloadAction<FeedMetrics[]>) {
      state.status = 'loaded';
      state.feedMetrics = action.payload;
      state.error = undefined;
    },
    fetchHistoricalMetricsSuccess(
      state,
      action: PayloadAction<Map<string, FeatureMetrics>>,
    ) {
      state.historicalMetrics = action.payload;
      state.status = 'loaded';
      state.error = undefined;
    },
    fetchNoticeMetricsSuccess(state, action: PayloadAction<NoticeMetrics[]>) {
      state.noticeMetrics = action.payload;
      state.status = 'loaded';
      state.error = undefined;
    },
    fetchFeaturesMetricsSuccess(
      state,
      action: PayloadAction<FeatureMetrics[]>,
    ) {
      state.featuresMetrics = action.payload;
      state.status = 'loaded';
      state.error = undefined;
    },
    fetchFeedMetricsFailure(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
      state.featuresMetrics = [];
    },
    fetchHistoricalMetricsFailure(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
      state.historicalMetrics = new Map();
    },
    fetchNoticeMetricsFailure(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
      state.noticeMetrics = [];
    },
    fetchFeaturesMetricsFailure(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
      state.featuresMetrics = [];
    },
  },
});

export const {
  fetchDataStart,
  fetchFeedMetricsSuccess,
  fetchHistoricalMetricsSuccess,
  fetchNoticeMetricsSuccess,
  fetchFeaturesMetricsSuccess,
  fetchFeedMetricsFailure,
  fetchHistoricalMetricsFailure,
  fetchNoticeMetricsFailure,
  fetchFeaturesMetricsFailure,
} = AnalyticsSlice.actions;

export default AnalyticsSlice.reducer;

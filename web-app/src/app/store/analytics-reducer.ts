import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type NoticeMetrics,
  type FeatureMetrics,
  type GTFSFeedMetrics,
  type AnalyticsFile,
} from '../screens/Analytics/types';

interface GTFSAnalyticsState {
  feedMetrics: GTFSFeedMetrics[];
  historicalMetrics: Map<string, FeatureMetrics>;
  noticeMetrics: NoticeMetrics[];
  featuresMetrics: FeatureMetrics[];
  status: 'loading' | 'loaded' | 'failed';
  error?: string;
  availableFiles: AnalyticsFile[];
  selectedFile?: string;
}

const initialState: GTFSAnalyticsState = {
  feedMetrics: [],
  historicalMetrics: new Map(),
  noticeMetrics: [],
  featuresMetrics: [],
  status: 'loading',
  error: undefined,
  availableFiles: [],
  selectedFile: undefined,
};

const GTFSAnalyticsSlice = createSlice({
  name: 'gtfsAnalytics',
  initialState,
  reducers: {
    fetchDataStart(state) {
      state.status = 'loading';
    },
    fetchFeedMetricsSuccess(state, action: PayloadAction<GTFSFeedMetrics[]>) {
      state.status = 'loaded';
      state.feedMetrics = action.payload;
      state.error = undefined;
    },
    fetchFeedMetricsFailure(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
      state.featuresMetrics = [];
    },
    fetchAvailableFilesStart(state) {
      state.availableFiles = [];
      state.selectedFile = undefined;
      state.status = 'loading';
    },
    fetchAvailableFilesSuccess(state, action: PayloadAction<AnalyticsFile[]>) {
      state.availableFiles = action.payload;
      state.status = 'loaded';
    },
    selectFile(state, action: PayloadAction<string>) {
      state.selectedFile = action.payload;
    },
  },
});

export const {
  fetchDataStart,
  fetchFeedMetricsSuccess,
  fetchFeedMetricsFailure,
  fetchAvailableFilesSuccess,
  fetchAvailableFilesStart,
  selectFile,
} = GTFSAnalyticsSlice.actions;

export default GTFSAnalyticsSlice.reducer;

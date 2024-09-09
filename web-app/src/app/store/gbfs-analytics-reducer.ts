import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type AnalyticsFile,
  type GBFSFeedMetrics,
} from '../screens/Analytics/types';

// Define the state interface
interface GBFSAnalyticsState {
  feedMetrics: GBFSFeedMetrics[];
  status: 'loading' | 'loaded' | 'failed';
  error?: string;
  availableFiles: AnalyticsFile[];
  selectedFile?: string;
}

// Set the initial state
const initialState: GBFSAnalyticsState = {
  feedMetrics: [],
  status: 'loading',
  error: undefined,
  availableFiles: [],
  selectedFile: undefined,
};

// Create the slice for GBFS analytics
const GBFSAnalyticsSlice = createSlice({
  name: 'gbfsAnalytics',
  initialState,
  reducers: {
    fetchDataStart(state) {
      state.status = 'loading';
    },
    fetchFeedMetricsSuccess(state, action: PayloadAction<GBFSFeedMetrics[]>) {
      state.status = 'loaded';
      state.feedMetrics = action.payload;
      state.error = undefined;
    },
    fetchFeedMetricsFailure(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
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
} = GBFSAnalyticsSlice.actions;

export default GBFSAnalyticsSlice.reducer;

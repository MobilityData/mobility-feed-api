import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type FeedErrors, FeedErrorSource, type FeedError } from '../types';
import { type paths } from '../services/feeds/types';
import { mergeAndSortDatasets } from '../utils/dataset';

interface DatasetState {
  status: 'loading' | 'loaded';
  datasetId: string | undefined;
  data:
    | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
    | undefined;
  loadedAllData?: boolean;
  errors: FeedErrors;
}

const initialState: DatasetState = {
  status: 'loading',
  datasetId: undefined,
  data: undefined,
  loadedAllData: false,
  errors: {
    [FeedErrorSource.DatabaseAPI]: null,
  },
};

export const datasetSlice = createSlice({
  name: 'dataset',
  initialState,
  reducers: {
    clearDataset: (state) => {
      state.data = initialState.data;
      state.loadedAllData = initialState.loadedAllData;
      state.errors = initialState.errors;
      state.status = initialState.status;
      state.datasetId = initialState.datasetId;
    },
    updateDatasetId: (
      state,
      action: PayloadAction<{
        datasetId: string;
      }>,
    ) => {
      state.datasetId = action.payload?.datasetId;
    },
    loadingDataset: (
      state,
      action: PayloadAction<{
        feedId: string;
        offset?: number;
        limit?: number;
      }>,
    ) => {
      state.status = 'loading';
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingDatasetSuccess: (
      state,
      action: PayloadAction<{
        data: paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];
        loadedAllData?: boolean;
      }>,
    ) => {
      state.status = 'loaded';
      state.loadedAllData = action.payload?.loadedAllData;
      state.data = mergeAndSortDatasets(action.payload?.data, state.data);
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingDatasetFail: (state, action: PayloadAction<FeedError>) => {
      state.errors.DatabaseAPI = action.payload;
    },
  },
});

export const {
  updateDatasetId,
  loadingDataset,
  loadingDatasetFail,
  loadingDatasetSuccess,
  clearDataset,
} = datasetSlice.actions;

export default datasetSlice.reducer;

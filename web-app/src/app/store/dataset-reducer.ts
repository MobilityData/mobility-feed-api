import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type FeedErrors, FeedErrorSource, type FeedError } from '../types';
import { type paths } from '../services/feeds/types';

interface DatasetState {
  status: 'loading' | 'loaded';
  datasetId: string | undefined;
  data:
    | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
    | undefined;
  errors: FeedErrors;
}

const initialState: DatasetState = {
  status: 'loading',
  datasetId: undefined,
  data: undefined,
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
      }>,
    ) => {
      state.status = 'loading';
      state.data = undefined;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingDatasetSuccess: (
      state,
      action: PayloadAction<{
        data: paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];
      }>,
    ) => {
      state.status = 'loaded';
      state.data = action.payload?.data.sort((a, b) => {
        if (a.downloaded_at !== undefined && b.downloaded_at !== undefined) {
          const dateB = new Date(b.downloaded_at).getTime();
          const dateA = new Date(a.downloaded_at).getTime();
          return dateB - dateA;
        }
        return 0;
      });
      // state.datasetId = action.payload.data?.id;
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

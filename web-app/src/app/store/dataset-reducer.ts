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
        accessToken: string;
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
      state.data = action.payload?.data;
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
} = datasetSlice.actions;

export default datasetSlice.reducer;

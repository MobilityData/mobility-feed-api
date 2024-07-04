import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type FeedErrors, FeedErrorSource, type FeedError } from '../types';
import {
  type AllFeedsParams,
  type AllFeedsType,
} from '../services/feeds/utils';

interface FeedsState {
  status: 'loading' | 'loaded' | 'error';
  data: AllFeedsType | undefined;
  errors: FeedErrors;
}

const initialState: FeedsState = {
  status: 'loading',
  data: undefined,
  errors: {
    [FeedErrorSource.DatabaseAPI]: null,
  },
};

export const feedsSlice = createSlice({
  name: 'feeds',
  initialState,
  reducers: {
    resetFeeds: (state) => {
      state.status = 'loaded';
      state.data = {
        total: 0,
        results: [],
      };
    },
    loadingFeeds: (
      state,
      action: PayloadAction<{
        params: AllFeedsParams;
      }>,
    ) => {
      state.status = 'loading';
      state.data = undefined;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingFeedsSuccess: (
      state,
      action: PayloadAction<{
        data: AllFeedsType;
      }>,
    ) => {
      state.status = 'loaded';
      state.data = action.payload.data;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingFeedsFail: (state, action: PayloadAction<FeedError>) => {
      state.status = 'error';
      state.errors.DatabaseAPI = action.payload;
    },
  },
});

export const {
  resetFeeds,
  loadingFeeds,
  loadingFeedsFail,
  loadingFeedsSuccess,
} = feedsSlice.actions;

export default feedsSlice.reducer;

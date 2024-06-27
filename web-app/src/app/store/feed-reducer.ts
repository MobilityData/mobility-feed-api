import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type FeedErrors, FeedErrorSource, type FeedError } from '../types';
import { type AllFeedType } from '../services/feeds/utils';

interface FeedState {
  status: 'loading' | 'loaded' | 'error';
  feedId: string | undefined;
  data: AllFeedType;
  errors: FeedErrors;
}

const initialState: FeedState = {
  status: 'loading',
  feedId: undefined,
  data: undefined,
  errors: {
    [FeedErrorSource.DatabaseAPI]: null,
  },
};

export const feedSlice = createSlice({
  name: 'feedProfile',
  initialState,
  reducers: {
    updateFeedId: (
      state,
      action: PayloadAction<{
        feedId: string;
      }>,
    ) => {
      state.feedId = action.payload?.feedId;
    },
    resetFeed: (state) => {
      state = {
        ...initialState,
      };
    },
    loadingFeed: (
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
    loadingFeedSuccess: (
      state,
      action: PayloadAction<{
        data: AllFeedType;
      }>,
    ) => {
      state.status = 'loaded';
      state.data = action.payload?.data;
      state.feedId = action.payload.data?.id;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingFeedFail: (state, action: PayloadAction<FeedError>) => {
      state.status = 'error';
      state.errors.DatabaseAPI = action.payload;
    },
  },
});

export const {
  updateFeedId,
  resetFeed,
  loadingFeed,
  loadingFeedFail,
  loadingFeedSuccess,
} = feedSlice.actions;

export default feedSlice.reducer;

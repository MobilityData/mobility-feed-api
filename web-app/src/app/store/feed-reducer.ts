import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type AppError } from '../types';
import { type AllFeedType } from '../services/feeds/utils';

interface FeedState {
  status: 'loading' | 'loaded' | 'loading_error';
  feedId: string | undefined;
  data: AllFeedType;
}

const initialState: FeedState = {
  status: 'loading',
  feedId: undefined,
  data: undefined,
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
    loadingFeed: (
      state,
      action: PayloadAction<{
        feedId: string;
        accessToken: string;
      }>,
    ) => {
      state.status = 'loading';
    },
    loadingFeedSuccess: (
      state,
      action: PayloadAction<{
        data: AllFeedType;
      }>,
    ) => {
      state.status = 'loaded';
      state.data = action.payload?.data;
    },
    loadingFeedFail: (state, action: PayloadAction<AppError>) => {
      state.status = 'loading_error';
      state.feedId = undefined;
      // state.errors = { ...initialState.errors, Feed: action.payload };
    },
  },
});

export const {
  updateFeedId,
  loadingFeed,
  loadingFeedFail,
  loadingFeedSuccess,
} = feedSlice.actions;

export default feedSlice.reducer;

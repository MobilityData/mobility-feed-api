import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type AppError } from '../types';
import { type paths } from '../services/feeds/types';

interface FeedState {
  status: 'loading' | 'loaded' | 'loading_error';
  feedId: string | undefined;
  data:
    | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
    | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
    | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
    | undefined;
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
        data:
          | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
          | paths['/v1/gtfs_feeds/{id}']['get']['responses'][200]['content']['application/json']
          | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
          | undefined;
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

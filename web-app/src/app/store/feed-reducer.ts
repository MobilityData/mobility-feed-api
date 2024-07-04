import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type FeedErrors,
  FeedErrorSource,
  type FeedError,
  type FeedStatus,
} from '../types';
import { type AllFeedType } from '../services/feeds/utils';

interface FeedState {
  status: FeedStatus;
  feedId: string | undefined;
  data: AllFeedType;
  relatedFeedIds: string[];
  relatedFeedsData: AllFeedType[];
  relatedFeedsStatus: 'loading' | 'loaded' | 'error';
  errors: FeedErrors;
}

const initialState: FeedState = {
  status: 'loaded',
  feedId: undefined,
  data: undefined,
  relatedFeedIds: [],
  relatedFeedsData: [],
  relatedFeedsStatus: 'loading',
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
    loadingRelatedFeeds: (
      state,
      action: PayloadAction<{
        feedIds: string[];
        accessToken: string;
      }>,
    ) => {
      state.relatedFeedsStatus = 'loading';
      state.relatedFeedsData = [];
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingRelatedFeedsSuccess: (
      state,
      action: PayloadAction<{
        data: AllFeedType[];
      }>,
    ) => {
      state.relatedFeedsStatus = 'loaded';
      state.relatedFeedsData = action.payload.data;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingRelatedFeedsFail: (state, action: PayloadAction<FeedError>) => {
      state.relatedFeedsStatus = 'error';
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
  loadingRelatedFeeds,
  loadingRelatedFeedsFail,
  loadingRelatedFeedsSuccess,
} = feedSlice.actions;

export default feedSlice.reducer;

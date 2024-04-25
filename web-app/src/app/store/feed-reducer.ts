import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type AppErrors, type AppError, ErrorSource } from '../types';
import { type AllFeedType } from '../services/feeds/utils';

interface FeedState {
  status: 'loading' | 'loaded';
  feedId: string | undefined;
  data: AllFeedType;
  errors: AppErrors;
}

const initialState: FeedState = {
  status: 'loading',
  feedId: undefined,
  data: undefined,
  errors: {
    [ErrorSource.SignUp]: null,
    [ErrorSource.Login]: null,
    [ErrorSource.Logout]: null,
    [ErrorSource.RefreshingAccessToken]: null,
    [ErrorSource.ChangePassword]: null,
    [ErrorSource.Registration]: null,
    [ErrorSource.ResetPassword]: null,
    [ErrorSource.VerifyEmail]: null,
    [ErrorSource.DatabaseAPI]: null,
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
    loadingFeed: (
      state,
      action: PayloadAction<{
        feedId: string;
        accessToken: string;
      }>,
    ) => {
      state.status = 'loading';
      state.data = undefined;
      state.errors = { ...initialState.errors };
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
      state.errors = { ...initialState.errors };
    },
    loadingFeedFail: (state, action: PayloadAction<AppError>) => {
      state.errors.DatabaseAPI = action.payload;
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

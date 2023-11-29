import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type AppError,
  type EmailLogin,
  type AppErrors,
  type User,
  type OauthProvider,
} from '../types';
import { type NavigateFunction } from 'react-router-dom';
import { type UserCredential } from 'firebase/auth';

interface UserProfileState {
  status:
    | 'unauthenticated'
    | 'login_in'
    | 'authenticated'
    | 'login_out'
    | 'sign_up'
    | 'loading_organization'
    | 'registered'
    | 'registering';
  isRefreshingAccessToken: boolean;
  isAppRefreshing: boolean;
  isRecoveryEmailSent: boolean;
  errors: AppErrors;
  user: User | undefined;
}

const initialState: UserProfileState = {
  status: 'unauthenticated',
  user: undefined,
  errors: {
    SignUp: null,
    Login: null,
    Logout: null,
    RefreshingAccessToken: null,
    Registration: null,
    ResetPassword: null,
  },
  isRefreshingAccessToken: false,
  isAppRefreshing: false,
  isRecoveryEmailSent: false,
};

export const userProfileSlice = createSlice({
  name: 'userProfile',
  initialState,
  reducers: {
    login: (state, action: PayloadAction<EmailLogin>) => {
      state.status = 'login_in';
      state.errors = { ...initialState.errors };
    },
    loginSuccess: (state, action: PayloadAction<User>) => {
      state.status = action.payload?.isRegistered
        ? 'registered'
        : 'authenticated';
      state.errors = { ...initialState.errors };
      state.user = action.payload;
    },
    authenticated: (state, action: PayloadAction<User>) => {
      state.status = action.payload?.isRegistered
        ? 'registered'
        : 'authenticated';
      state.errors = { ...initialState.errors };
      state.user = action.payload;
    },
    loginFail: (state, action: PayloadAction<AppError>) => {
      state.errors = { ...initialState.errors, Login: action.payload };
      state.status = 'unauthenticated';
    },
    logout: (
      state,
      action: PayloadAction<{
        redirectScreen: string;
        navigateTo: NavigateFunction;
      }>,
    ) => {
      state.status = 'login_out';
      state.errors = { ...initialState.errors };
    },
    logoutSuccess: (state) => {
      state.status = 'unauthenticated';
    },
    logoutFail: (state) => {
      state.status = 'unauthenticated';
    },
    signUp: (
      state,
      action: PayloadAction<{
        email: string;
        password: string;
        redirectScreen: string;
        navigateTo: NavigateFunction;
      }>,
    ) => {
      state.status = 'sign_up';
      state.errors = { ...initialState.errors };
    },
    signUpSuccess: (state, action: PayloadAction<User>) => {
      state.status = state.status = action.payload?.isRegistered
        ? 'registered'
        : 'authenticated';
      state.user = action.payload;
      state.errors = { ...initialState.errors };
    },
    signUpFail: (state, action: PayloadAction<AppError>) => {
      state.status = 'unauthenticated';
      state.errors = { ...initialState.errors, SignUp: action.payload };
    },
    resetProfileErrors: (state) => {
      state.errors = { ...initialState.errors };
    },
    requestRefreshAccessToken: (state) => {
      state.isRefreshingAccessToken = true;
      state.errors = { ...initialState.errors };
    },
    refreshAccessToken: (state, action: PayloadAction<User>) => {
      if (state.user !== undefined && state.status === 'registered') {
        state.user.accessToken = action.payload.accessToken;
        state.user.accessTokenExpirationTime =
          action.payload.accessTokenExpirationTime;
      }
      state.isRefreshingAccessToken = false;
    },
    refreshAccessTokenFail: (state, action: PayloadAction<AppError>) => {
      state.isRefreshingAccessToken = false;
      state.errors.RefreshingAccessToken = action.payload;
    },
    loginWithProvider: (
      state,
      action: PayloadAction<{
        oauthProvider: OauthProvider;
        userCredential: UserCredential;
      }>,
    ) => {
      state.errors = { ...initialState.errors };
    },
    refreshUserInformation: (
      state,
      action: PayloadAction<{
        fullName: string;
        organization: string;
        isRegisteredToReceiveAPIAnnouncements: boolean;
      }>,
    ) => {
      if (state.user !== undefined) {
        state.errors.Registration = null;
        state.user.fullName = action.payload?.fullName ?? '';
        state.user.organization = action.payload?.organization ?? 'Unknown';
        state.user.isRegisteredToReceiveAPIAnnouncements =
          action.payload?.isRegisteredToReceiveAPIAnnouncements ?? false;
        state.status = 'registering';
      }
    },
    refreshUserInformationFail: (state, action: PayloadAction<AppError>) => {
      state.errors.Registration = action.payload;
      state.status = 'authenticated';
    },
    refreshUserInformationSuccess: (state) => {
      state.errors.Registration = null;
      state.status = 'registered';
    },
    refreshApp: (state) => {
      state.isAppRefreshing = true;
    },
    refreshAppSuccess: (state) => {
      state.isAppRefreshing = false;
    },
    resetPassword: (state, action: PayloadAction<string>) => {
      if (state.status === 'unauthenticated') {
        state.isRecoveryEmailSent = false;
        state.errors = { ...initialState.errors };
        state.isAppRefreshing = true;
      }
    },
    resetPasswordFail: (state, action: PayloadAction<AppError>) => {
      state.isRecoveryEmailSent = false;
      state.errors.ResetPassword = action.payload;
      state.isAppRefreshing = false;
    },
    resetPasswordSuccess: (state) => {
      state.isRecoveryEmailSent = true;
      state.errors.ResetPassword = null;
      state.isAppRefreshing = false;
    },
  },
});

export const {
  login,
  loginSuccess,
  loginFail,
  logout,
  logoutSuccess,
  logoutFail,
  signUp,
  signUpSuccess,
  signUpFail,
  resetProfileErrors,
  refreshAccessToken,
  refreshAccessTokenFail,
  requestRefreshAccessToken,
  loginWithProvider,
  refreshUserInformation,
  refreshUserInformationFail,
  refreshUserInformationSuccess,
  refreshApp,
  refreshAppSuccess,
  resetPassword,
  resetPasswordFail,
  resetPasswordSuccess,
} = userProfileSlice.actions;

export default userProfileSlice.reducer;

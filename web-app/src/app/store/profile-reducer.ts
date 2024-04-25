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
    | 'unverified'
    | 'login_out'
    | 'sign_up'
    | 'loading_organization'
    | 'registered'
    | 'registering'
    | 'anonymous_login';
  isRefreshingAccessToken: boolean;
  isAppRefreshing: boolean;
  isRecoveryEmailSent: boolean;
  isVerificationEmailSent: boolean;
  errors: AppErrors;
  user: User | undefined;
  changePasswordStatus: 'idle' | 'loading' | 'success' | 'fail';
  isSignedInWithProvider: boolean;
}

const initialState: UserProfileState = {
  status: 'unauthenticated',
  user: undefined,
  errors: {
    SignUp: null,
    Login: null,
    Logout: null,
    RefreshingAccessToken: null,
    ChangePassword: null,
    Registration: null,
    ResetPassword: null,
    VerifyEmail: null,
    DatabaseAPI: null,
  },
  isRefreshingAccessToken: false,
  isVerificationEmailSent: false,
  isAppRefreshing: false,
  changePasswordStatus: 'idle',
  isSignedInWithProvider: false,
  isRecoveryEmailSent: false,
};

export const userProfileSlice = createSlice({
  name: 'userProfile',
  initialState,
  reducers: {
    login: (state, action: PayloadAction<EmailLogin>) => {
      state.status = 'login_in';
      state.errors = { ...initialState.errors };
      state.isAppRefreshing = true;
    },
    loginSuccess: (state, action: PayloadAction<User>) => {
      state.status = action.payload?.isRegistered
        ? 'registered'
        : action.payload?.isEmailVerified
          ? 'authenticated'
          : action.payload?.isAnonymous
            ? 'anonymous_login'
            : 'unverified';
      state.errors = { ...initialState.errors };
      state.user = action.payload;
      state.isAppRefreshing = false;
    },
    loginFail: (state, action: PayloadAction<AppError>) => {
      state.errors = { ...initialState.errors, Login: action.payload };
      state.status = 'unauthenticated';
      state.isAppRefreshing = false;
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
      state.isAppRefreshing = true;
    },
    logoutSuccess: (state) => {
      state.status = 'unauthenticated';
      state.isSignedInWithProvider = false;
      state.isAppRefreshing = false;
    },
    logoutFail: (state) => {
      state.status = 'unauthenticated';
      state.isAppRefreshing = false;
    },
    signUp: (
      state,
      action: PayloadAction<{
        email: string;
        password: string;
      }>,
    ) => {
      state.status = 'sign_up';
      state.errors = { ...initialState.errors };
      state.isAppRefreshing = true;
    },
    signUpSuccess: (state, action: PayloadAction<User>) => {
      state.status = state.status = action.payload?.isEmailVerified
        ? 'authenticated'
        : 'unverified';
      state.user = action.payload;
      state.errors = { ...initialState.errors };
      state.isAppRefreshing = false;
    },
    signUpFail: (state, action: PayloadAction<AppError>) => {
      state.status = 'unauthenticated';
      state.errors = { ...initialState.errors, SignUp: action.payload };
      state.isAppRefreshing = false;
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
      state.isSignedInWithProvider = true;
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
    changePasswordInit: (state) => {
      state.errors.ChangePassword = null;
      state.changePasswordStatus = 'idle';
    },
    changePassword: (
      state,
      action: PayloadAction<{
        oldPassword: string;
        newPassword: string;
      }>,
    ) => {
      state.isAppRefreshing = true;
      state.errors.ChangePassword = null;
      state.changePasswordStatus = 'loading';
    },
    changePasswordSuccess: (state) => {
      state.isAppRefreshing = false;
      state.errors.ChangePassword = null;
      state.changePasswordStatus = 'success';
    },
    changePasswordFail: (state, action: PayloadAction<AppError>) => {
      state.isAppRefreshing = false;
      state.errors.ChangePassword = action.payload;
      state.changePasswordStatus = 'fail';
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
    verifyEmail: (state) => {
      state.isAppRefreshing = true;
      state.isVerificationEmailSent = false;
      state.errors = { ...initialState.errors };
    },
    verifySuccess: (state) => {
      state.isAppRefreshing = false;
      state.isVerificationEmailSent = true;
      state.errors = { ...initialState.errors };
    },
    verifyFail: (state, action: PayloadAction<AppError>) => {
      state.errors.VerifyEmail = action.payload;
      state.isAppRefreshing = false;
      state.isVerificationEmailSent = false;
    },
    emailVerified: (state) => {
      if (state.user !== undefined) {
        state.user.isEmailVerified = true;
        state.status = state.user.isRegistered ? 'registered' : 'authenticated';
        state.errors = { ...initialState.errors };
      }
      state.isAppRefreshing = false;
    },
    anonymousLogin: (state) => {
      state.isAppRefreshing = true;
    },
    anonymousLoginFailed: (state) => {
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
  changePassword,
  changePasswordInit,
  changePasswordSuccess,
  changePasswordFail,
  refreshApp,
  refreshAppSuccess,
  resetPassword,
  resetPasswordFail,
  resetPasswordSuccess,
  verifyEmail,
  verifySuccess,
  verifyFail,
  emailVerified,
  anonymousLogin,
  anonymousLoginFailed,
} = userProfileSlice.actions;

export default userProfileSlice.reducer;

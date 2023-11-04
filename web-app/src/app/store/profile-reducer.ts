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
    | 'registered'
    | 'registering';
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
    Registration: null,
  },
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
      state.status = 'authenticated';
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
    logoutSucess: (state) => {
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
      state.status = 'authenticated';
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
    requestRefreshAccessToken: (state) => {},
    refreshAccessToken: (state, action: PayloadAction<User>) => {
      if (state.user !== undefined && state.status === 'authenticated') {
        state.user.accessToken = action.payload.accessToken;
        state.user.accessTokenExpirationTime =
          action.payload.accessTokenExpirationTime;
      }
    },
    loginWithProvider: (
      state,
      action: PayloadAction<{
        oauthProvider: OauthProvider;
        userCredential: UserCredential;
      }>,
    ) => {
      state.status = 'authenticated';
      state.errors = { ...initialState.errors };
    },
    refreshUserInformation: (
      state,
      action: PayloadAction<{ fullname: string; organization: string }>,
    ) => {
      if (state.user !== undefined && state.status === 'authenticated') {
        state.errors.Registration = null;
        state.user.fullname = action.payload?.fullname ?? '';
        state.user.organization = action.payload?.organization ?? 'Unknown';
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
  },
});

export const {
  login,
  loginSuccess,
  loginFail,
  logout,
  logoutSucess,
  logoutFail,
  signUp,
  signUpSuccess,
  signUpFail,
  resetProfileErrors,
  refreshAccessToken,
  requestRefreshAccessToken,
  loginWithProvider,
  refreshUserInformation,
  refreshUserInformationFail,
  refreshUserInformationSuccess,
} = userProfileSlice.actions;

export default userProfileSlice.reducer;

import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type RootState } from './store';
import { type AppError, type EmailLogin } from '../types';
import { type NavigateFunction } from 'react-router-dom';

interface User {
  fullname: string | undefined;
  email: string | undefined;
  organization: string | undefined;
}

interface UserProfileState {
  status: 'unauthenticated' | 'login_in' | 'authenticated' | 'login_out';
  loginError: AppError | null;
  user: User | undefined;
}

// type  = ProfileState & User;

const initialState: UserProfileState = {
  status: 'unauthenticated',
  user: undefined,
  loginError: null,
};

export const userProfileSlice = createSlice({
  name: 'userProfile',
  initialState,
  reducers: {
    login: (state, action: PayloadAction<EmailLogin>) => {
      state.status = 'login_in';
      state.loginError = null;
    },
    loginSuccess: (state, action: PayloadAction<User>) => {
      state.status = 'authenticated';
      state.loginError = null;
    },
    loginFail: (state, action: PayloadAction<AppError>) => {
      state.loginError = action.payload;
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
      state.loginError = null;
    },
    logoutSucess: (state) => {
      state.status = 'unauthenticated';
      state.loginError = null;
    },
  },
});

export const { login, loginSuccess, loginFail, logout } =
  userProfileSlice.actions;

export const selectUserProfile = (state: RootState): User | undefined =>
  state.userProfile.user;

export const selectIsAuthenticated = (state: RootState): boolean =>
  state.userProfile.status === 'authenticated';

export const selectEmailLoginError = (state: RootState): AppError | null =>
  state.userProfile.loginError;

export default userProfileSlice.reducer;

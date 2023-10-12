import { type AppError, ErrorSource, type User } from '../types';
import { type RootState } from './store';

export const selectUserProfile = (state: RootState): User | undefined =>
  state.userProfile.user;

export const selectIsAuthenticated = (state: RootState): boolean =>
  state.userProfile.status === 'authenticated' ||
  state.userProfile.status === 'loading_organization';

export const selectErrorBySource = (
  state: RootState,
  source: ErrorSource,
): AppError | null => state.userProfile.errors[source];

export const selectEmailLoginError = (state: RootState): AppError | null =>
  selectErrorBySource(state, ErrorSource.Login);

export const selectSignUpError = (state: RootState): AppError | null =>
  selectErrorBySource(state, ErrorSource.SignUp);

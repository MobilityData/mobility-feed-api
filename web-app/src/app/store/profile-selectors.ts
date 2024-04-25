import { type ProfileError, ProfileErrorSource, type User } from '../types';
import { type RootState } from './store';

export const selectUserProfile = (state: RootState): User | undefined =>
  state.userProfile.user;

export const selectIsAuthenticated = (state: RootState): boolean =>
  state.userProfile.status === 'authenticated' ||
  state.userProfile.status === 'registered' ||
  state.userProfile.status === 'unverified';

export const selectUserProfileStatus = (state: RootState): string =>
  state.userProfile.status;

export const selectIsTokenRefreshed = (state: RootState): boolean =>
  !state.userProfile.isRefreshingAccessToken &&
  state.userProfile.errors.RefreshingAccessToken === null;

export const selectIsVerificationEmailSent = (state: RootState): boolean =>
  state.userProfile.isVerificationEmailSent;

export const selectErrorBySource = (
  state: RootState,
  source: ProfileErrorSource,
): ProfileError | null => state.userProfile.errors[source];

export const selectEmailLoginError = (state: RootState): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.Login);

export const selectEmailVerificationError = (
  state: RootState,
): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.VerifyEmail);

export const selectResetPasswordError = (
  state: RootState,
): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.ResetPassword);

export const selectIsRecoveryEmailSent = (state: RootState): boolean =>
  state.userProfile.isRecoveryEmailSent;

export const selectSignUpError = (state: RootState): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.SignUp);

export const selectRefreshingAccessTokenError = (
  state: RootState,
): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.RefreshingAccessToken);

export const selectIsRefreshingAccessToken = (state: RootState): boolean =>
  state.userProfile.isRefreshingAccessToken;

export const selectSignedInWithProvider = (state: RootState): boolean =>
  state.userProfile.isSignedInWithProvider;

export const selectChangePasswordError = (
  state: RootState,
): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.ChangePassword);

export const selectChangePasswordStatus = (state: RootState): string =>
  state.userProfile.changePasswordStatus;

export const selectRegistrationError = (
  state: RootState,
): ProfileError | null =>
  selectErrorBySource(state, ProfileErrorSource.Registration);

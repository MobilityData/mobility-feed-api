import { app } from '../../../firebase';
import { type PayloadAction } from '@reduxjs/toolkit';
import { call, put, select, takeLatest } from 'redux-saga/effects';
import {
  USER_PROFILE_LOGIN,
  USER_PROFILE_LOGOUT,
  USER_PROFILE_SIGNUP,
  type User,
  type OauthProvider,
  USER_PROFILE_LOGIN_WITH_PROVIDER,
  USER_PROFILE_CHANGE_PASSWORD,
  USER_PROFILE_RESET_PASSWORD,
  type UserData,
  USER_PROFILE_SEND_VERIFICATION_EMAIL,
  USER_PROFILE_ANONYMOUS_LOGIN,
  type ProfileError,
} from '../../types';
import 'firebase/compat/auth';
import {
  changePasswordFail,
  changePasswordSuccess,
  loginFail,
  loginSuccess,
  logoutSuccess,
  signUpFail,
  signUpSuccess,
  resetPasswordFail,
  resetPasswordSuccess,
  verifyFail,
  verifySuccess,
  anonymousLoginFailed,
} from '../profile-reducer';
import { type NavigateFunction } from 'react-router-dom';
import {
  getUserFromSession,
  populateUserWithAdditionalInfo,
  retrieveUserInformation,
  sendEmailVerification,
} from '../../services';
import {
  type AdditionalUserInfo,
  type UserCredential,
  getAdditionalUserInfo,
  reauthenticateWithCredential,
  EmailAuthProvider,
  getAuth,
  sendPasswordResetEmail,
  signInAnonymously,
} from 'firebase/auth';
import { getAppError } from '../../utils/error';
import { selectIsAuthenticated } from '../profile-selectors';

function* emailLoginSaga({
  payload: { email, password },
}: PayloadAction<{ email: string; password: string }>): Generator<
  unknown,
  void,
  User
> {
  try {
    yield app.auth().signInWithEmailAndPassword(email, password);
    const user = yield call(getUserFromSession);
    const userData = (yield call(retrieveUserInformation)) as UserData;
    const userEnhanced = populateUserWithAdditionalInfo(
      user,
      userData,
      undefined,
    );
    yield put(loginSuccess(userEnhanced));
  } catch (error) {
    yield put(loginFail(getAppError(error) as ProfileError));
  }
}

function* logoutSaga({
  payload: { redirectScreen, navigateTo },
}: PayloadAction<{
  redirectScreen: string;
  navigateTo: NavigateFunction;
}>): Generator {
  try {
    navigateTo(redirectScreen);
    yield app.auth().signOut();
    yield put(logoutSuccess());
  } catch (error) {
    yield put(loginFail(getAppError(error) as ProfileError));
  }
}

function* signUpSaga({
  payload: { email, password },
}: PayloadAction<{
  email: string;
  password: string;
}>): Generator {
  try {
    yield app.auth().createUserWithEmailAndPassword(email, password);
    yield call(sendEmailVerification);
    const user = yield call(getUserFromSession);
    if (user === null) {
      throw new Error('User not found');
    }
    yield put(signUpSuccess(user as User));
  } catch (error) {
    yield put(signUpFail(getAppError(error) as ProfileError));
  }
}

function* changePasswordSaga({
  payload: { oldPassword, newPassword },
}: PayloadAction<{
  oldPassword: string;
  newPassword: string;
}>): Generator {
  const user = app.auth().currentUser;
  if (user === null) {
    throw new Error('User not found');
  }
  if (user.email === null) {
    throw new Error('User email not found');
  }
  const credential = EmailAuthProvider.credential(user.email, oldPassword);
  try {
    yield reauthenticateWithCredential(user, credential);
    yield user.updatePassword(newPassword);
    yield put(changePasswordSuccess());
  } catch (error) {
    yield put(changePasswordFail(getAppError(error) as ProfileError));
  }
}

function* sendEmailVerificationSaga(): Generator {
  try {
    yield call(sendEmailVerification);
    yield put(verifySuccess());
  } catch (error) {
    yield put(verifyFail(getAppError(error) as ProfileError));
  }
}

function* loginWithProviderSaga({
  payload: { oauthProvider, userCredential },
}: PayloadAction<{
  oauthProvider: OauthProvider;
  userCredential: UserCredential;
}>): Generator {
  try {
    const user = (yield call(getUserFromSession)) as User;
    const additionalUserInfo = (yield call(
      getAdditionalUserInfo,
      userCredential,
    )) as AdditionalUserInfo;
    const userData = (yield call(retrieveUserInformation)) as UserData;
    const userEnhanced = populateUserWithAdditionalInfo(
      user,
      userData,
      additionalUserInfo,
    );
    yield put(loginSuccess(userEnhanced));
  } catch (error) {
    yield put(loginFail(getAppError(error) as ProfileError));
  }
}

function* resetPasswordSaga({
  payload: email,
}: PayloadAction<string>): Generator {
  try {
    const auth = getAuth();
    yield call(async () => {
      await sendPasswordResetEmail(auth, email);
    });
    yield put(resetPasswordSuccess());
  } catch (error) {
    yield put(resetPasswordFail(getAppError(error) as ProfileError));
  }
}

function* anonymousLoginSaga(): Generator {
  try {
    // Check if the user is already authenticated
    const isAuthenticated: boolean = (yield select(
      selectIsAuthenticated,
    )) as boolean;
    if (isAuthenticated) {
      yield put(anonymousLoginFailed()); // fails silently
      return;
    }

    // Sign in anonymously
    const auth = getAuth();
    yield call(async () => {
      await signInAnonymously(auth);
    });
    const user = yield call(getUserFromSession);
    if (user === null) {
      throw new Error('User not found');
    }
    const firebaseUser = app.auth().currentUser;
    if (firebaseUser === null) {
      throw new Error('Firebase user not found');
    }
    const currentUser = {
      ...user,
      refreshToken: firebaseUser.refreshToken,
    };
    yield put(loginSuccess(currentUser as User));
  } catch (error) {
    yield put(anonymousLoginFailed()); // fails silently
  }
}

export function* watchAuth(): Generator {
  yield takeLatest(USER_PROFILE_LOGIN, emailLoginSaga);
  yield takeLatest(USER_PROFILE_LOGOUT, logoutSaga);
  yield takeLatest(USER_PROFILE_SIGNUP, signUpSaga);
  yield takeLatest(
    USER_PROFILE_SEND_VERIFICATION_EMAIL,
    sendEmailVerificationSaga,
  );
  yield takeLatest(USER_PROFILE_LOGIN_WITH_PROVIDER, loginWithProviderSaga);
  yield takeLatest(USER_PROFILE_CHANGE_PASSWORD, changePasswordSaga);
  yield takeLatest(USER_PROFILE_RESET_PASSWORD, resetPasswordSaga);
  yield takeLatest(USER_PROFILE_ANONYMOUS_LOGIN, anonymousLoginSaga);
}

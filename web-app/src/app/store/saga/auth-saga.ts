import { app } from '../../../firebase';
import { type PayloadAction } from '@reduxjs/toolkit';
import { type StrictEffect, call, put, takeLatest } from 'redux-saga/effects';
import {
  type AppError,
  USER_PROFILE_LOGIN,
  USER_PROFILE_LOGOUT,
  USER_PROFILE_SIGNUP,
  type User,
} from '../../types';
import 'firebase/compat/auth';
import {
  loginFail,
  loginSuccess,
  logoutSucess,
  signUpFail,
  signUpSuccess,
} from '../profile-reducer';
import { FirebaseError } from '@firebase/util';
import { type NavigateFunction } from 'react-router-dom';
import { getUserFromSession, sendEmailVerification } from '../../services';

const getAppError = (error: unknown): AppError => {
  const appError: AppError = {
    code: 'unknown',
    message: 'Unknown error',
  };
  if (error instanceof FirebaseError) {
    appError.code = error.code;
    let message = error.message;
    if (error.message.startsWith('Firebase: ')) {
      message = error.message.substring('Firebase: '.length);
    }
    appError.message = message;
  } else {
    appError.message = error as string;
  }
  return appError;
};

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
    yield put(loginSuccess(user));
  } catch (error) {
    yield put(loginFail(getAppError(error)));
  }
}

function* logoutSaga({
  payload: { redirectScreen, navigateTo },
}: PayloadAction<{
  redirectScreen: string;
  navigateTo: NavigateFunction;
}>): Generator {
  try {
    yield app.auth().signOut();
    yield put(logoutSucess());
    navigateTo(redirectScreen);
  } catch (error) {
    yield put(loginFail(getAppError(error)));
  }
}

function* signUpSaga({
  payload: { email, password, redirectScreen, navigateTo },
}: PayloadAction<{
  email: string;
  password: string;
  redirectScreen: string;
  navigateTo: NavigateFunction;
}>): Generator<StrictEffect, void, User> {
  try {
    yield call(app.auth().createUserWithEmailAndPassword, email, password);
    const user = yield call(getUserFromSession);
    yield put(signUpSuccess(user));
    yield call(sendEmailVerification);
    navigateTo(redirectScreen);
  } catch (error) {
    yield put(signUpFail(getAppError(error)));
  }
}

export function* watchAuth(): Generator {
  yield takeLatest(USER_PROFILE_LOGIN, emailLoginSaga);
  yield takeLatest(USER_PROFILE_LOGOUT, logoutSaga);
  yield takeLatest(USER_PROFILE_SIGNUP, signUpSaga);
}

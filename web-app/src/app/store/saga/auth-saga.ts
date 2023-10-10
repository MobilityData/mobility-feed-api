import { app } from '../../../firebase';
import { type PayloadAction } from '@reduxjs/toolkit';
import { put, takeLatest } from 'redux-saga/effects';
import {
  type AppError,
  USER_PROFILE_LOGIN,
  USER_PROFILE_LOGOUT,
  USER_PROFILE_LOGOUT_SUCCESS,
  USER_PROFILE_LOGIN_SUCCESS,
} from '../../types';
import 'firebase/compat/auth';
import { loginFail } from '../profile-reducer';
import { FirebaseError } from '@firebase/util';
import { type NavigateFunction } from 'react-router-dom';

const getAppError = (error: unknown): AppError => {
  const appError: AppError = {
    code: 'unknown',
    message: 'Unknown error',
  };
  if (error instanceof FirebaseError) {
    appError.code = error.code;
    appError.message = error.message;
  } else {
    appError.message = error as string;
  }
  return appError;
};

// Generator function
function* emailLoginSaga({
  payload: { email, password },
}: PayloadAction<{ email: string; password: string }>): Generator {
  try {
    yield app.auth().signInWithEmailAndPassword(email, password);
    yield put({ type: USER_PROFILE_LOGIN_SUCCESS });
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
    yield put({ type: USER_PROFILE_LOGOUT_SUCCESS });
    navigateTo(redirectScreen);
  } catch (error) {
    yield put(loginFail(getAppError(error)));
  }
}

export function* watchAuth(): Generator {
  yield takeLatest(USER_PROFILE_LOGIN, emailLoginSaga);
  yield takeLatest(USER_PROFILE_LOGOUT, logoutSaga);
}

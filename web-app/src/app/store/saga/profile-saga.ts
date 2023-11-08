import {
  type StrictEffect,
  call,
  takeLatest,
  put,
  select,
} from 'redux-saga/effects';
import {
  USER_PROFILE_REFRESH_INFORMATION,
  USER_REQUEST_REFRESH_ACCESS_TOKEN,
  type User,
} from '../../types';
import { generateUserAccessToken, updateUserInformation } from '../../services';
import {
  refreshAccessToken,
  refreshAccessTokenFail,
  refreshUserInformationFail,
  refreshUserInformationSuccess,
} from '../profile-reducer';
import { getAppError } from '../../utils/error';
import { selectUserProfile } from '../profile-selectors';

function* refreshAccessTokenSaga(): Generator<StrictEffect, void, User> {
  try {
    const user = yield call(generateUserAccessToken);
    if (user !== null) {
      yield put(refreshAccessToken(user));
    }
  } catch (error) {
    yield put(refreshAccessTokenFail(getAppError(error)));
  }
}

function* refreshUserInformation(): Generator<StrictEffect, void, User> {
  try {
    const user = yield select(selectUserProfile);
    if (user?.fullname !== undefined) {
      yield call(updateUserInformation, { fullname: user.fullname });
      yield put(refreshUserInformationSuccess());
    }
  } catch (error) {
    yield put(refreshUserInformationFail(getAppError(error)));
  }
}

export function* watchProfile(): Generator {
  yield takeLatest(USER_REQUEST_REFRESH_ACCESS_TOKEN, refreshAccessTokenSaga);
  yield takeLatest(USER_PROFILE_REFRESH_INFORMATION, refreshUserInformation);
}

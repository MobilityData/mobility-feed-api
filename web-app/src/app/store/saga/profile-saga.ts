import { type StrictEffect, call, takeLatest, put } from 'redux-saga/effects';
import {
  USER_PROFILE_LOAD_ORGANIZATION,
  USER_PROFILE_LOAD_ORGANIZATION_SUCCESS,
  USER_REQUEST_REFRESH_ACCESS_TOKEN,
  type User,
} from '../../types';
import { generateUserAccessToken, getUserOrganization } from '../../services';
import { refreshAccessToken } from '../profile-reducer';

function* loadUserOrganizationSaga(): Generator<StrictEffect, void, User> {
  try {
    const organization = yield call(getUserOrganization);
    console.log(organization);
  } catch (error) {}
}

function* refreshAccessTokenSaga(): Generator<StrictEffect, void, User> {
  try {
    const user = yield call(generateUserAccessToken);
    if (user !== null) {
      yield put(refreshAccessToken(user));
    }
  } catch (error) {
    // ignore
  }
}

// eslint-disable-next-line require-yield
function* saveUserOrganizationSaga(): Generator<StrictEffect, void, User> {
  throw new Error('Not implemented');
}

export function* watchProfile(): Generator {
  yield takeLatest(USER_PROFILE_LOAD_ORGANIZATION, loadUserOrganizationSaga);
  yield takeLatest(
    USER_PROFILE_LOAD_ORGANIZATION_SUCCESS,
    saveUserOrganizationSaga,
  );
  yield takeLatest(USER_REQUEST_REFRESH_ACCESS_TOKEN, refreshAccessTokenSaga);
}

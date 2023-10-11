import { type StrictEffect, call, takeLatest } from 'redux-saga/effects';
import {
  USER_PROFILE_LOAD_ORGANIZATION,
  USER_PROFILE_LOAD_ORGANIZATION_SUCCESS,
  type User,
} from '../../types';
import { getUserOrganization } from '../../services';

function* loadUserOrganizationSaga(): Generator<StrictEffect, void, User> {
  try {
    const organization = yield call(getUserOrganization);
    console.log(organization);
  } catch (error) {}
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
}

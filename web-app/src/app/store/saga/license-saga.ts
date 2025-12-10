import {
  type StrictEffect,
  call,
  takeLatest,
  put,
  select,
} from 'redux-saga/effects';
import {
  loadingLicenseFail,
  loadingLicenseSuccess,
  type License,
} from '../license-reducer';
import { getAppError } from '../../utils/error';
import {
  LICENSE_PROFILE_LOADING_LICENSE,
  type LicenseError,
} from '../../types';
import { type PayloadAction } from '@reduxjs/toolkit';
import { getLicense } from '../../services/feeds';
import { getUserAccessToken } from '../../services';
import { selectLicenseData } from '../license-selectors';

export function* getLicenseSaga({
  payload: { licenseId },
}: PayloadAction<{ licenseId: string }>): Generator<
  StrictEffect,
  void,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any
> {
  try {
    const licensesData = (yield select(selectLicenseData)) as Record<
      string,
      { license: License; fetchedAt: number }
    >;
    const cachedLicense = licensesData[licenseId];
    const now = Date.now();
    const oneHour = 60 * 60 * 1000;

    if (cachedLicense != null && now - cachedLicense.fetchedAt < oneHour) {
      yield put(
        loadingLicenseSuccess({
          license: cachedLicense.license,
          fetchedAt: cachedLicense.fetchedAt,
        }),
      );
      return;
    }

    if (licenseId !== undefined) {
      const accessToken = (yield call(getUserAccessToken)) as string;
      const license = (yield call(
        getLicense,
        licenseId,
        accessToken,
      )) as License;
      yield put(
        loadingLicenseSuccess({
          license,
          fetchedAt: Date.now(),
        }),
      );
    }
  } catch (error) {
    yield put(loadingLicenseFail(getAppError(error) as LicenseError));
  }
}

export function* watchLicense(): Generator {
  yield takeLatest(LICENSE_PROFILE_LOADING_LICENSE, getLicenseSaga);
}

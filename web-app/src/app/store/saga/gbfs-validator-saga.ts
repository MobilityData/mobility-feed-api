import { call, put, takeLatest } from 'redux-saga/effects';
import {
  validateStart,
  validateSuccess,
  validateFailure,
  type ValidateRequestBody,
} from '../gbfs-validator-reducer';
import { getEnvConfig } from '../../utils/config';
import type { components } from '../../services/feeds/gbfs-validator-types';

const getValidatorBaseUrl = (): string =>
  getEnvConfig('REACT_APP_GBFS_VALIDATOR_API_BASE_URL');

function* runValidation(
  action: ReturnType<typeof validateStart>,
): Generator<unknown, void, never> {
  try {
    const payload: ValidateRequestBody = action.payload;
    const url = `${getValidatorBaseUrl().replace(/\/$/, '')}/validate`;
    const response: Response = yield call(fetch, url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const text: string = yield response.text();
      console.error('Validator response error text:', text);
      throw new Error(
        `Validator error ${response.status}: ${response.statusText} - ${text}`,
      );
    }
    const data: components['schemas']['ValidationResult'] =
      yield response.json();

    yield put(validateSuccess(data));
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Unknown error';
    yield put(validateFailure(msg));
  }
}

export function* watchGbfsValidator(): Generator<unknown, void, unknown> {
  yield takeLatest(validateStart.type, runValidation);
}

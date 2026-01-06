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
  getEnvConfig('NEXT_PUBLIC_GBFS_VALIDATOR_API_BASE_URL');

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
      throw new Error(
        `Validator error ${response.status}: ${response.statusText} - ${text}`,
      );
    }
    const data: components['schemas']['ValidationResult'] =
      yield response.json();

    const allSystemErrors = data?.summary?.files?.flatMap(
      (file) => file.systemErrors ?? [],
    );

    const allFilesHaveSystemErrors =
      data?.summary?.files != null &&
      data.summary.files.length > 0 &&
      data.summary.files.every((file) => (file.systemErrors?.length ?? 0) > 0);

    // If all files have system errors, treat it as a failure
    if (allFilesHaveSystemErrors) {
      throw new Error(
        `Validation failed due to system errors: ${allSystemErrors
          ?.map((e) => e.error + ' : ' + e.message)
          .join('; ')}`,
      );
    }

    yield put(validateSuccess(data));
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Unknown error';
    yield put(validateFailure(msg));
  }
}

export function* watchGbfsValidator(): Generator<unknown, void, unknown> {
  yield takeLatest(validateStart.type, runValidation);
}

import { all } from 'redux-saga/effects';
import { watchAuth } from './auth-saga';
import { watchProfile } from './profile-saga';

const rootSaga = function* (): Generator {
  yield all([watchAuth(), watchProfile()]);
};

export default rootSaga;

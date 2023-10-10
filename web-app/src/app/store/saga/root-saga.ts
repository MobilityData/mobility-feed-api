import { all, fork } from 'redux-saga/effects';
import { watchAuth } from './auth-saga';

const rootSaga = function* (): Generator {
  yield all([fork(watchAuth)]);
};

export default rootSaga;

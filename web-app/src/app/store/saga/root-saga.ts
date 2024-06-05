import { all } from 'redux-saga/effects';
import { watchAuth } from './auth-saga';
import { watchProfile } from './profile-saga';
import { watchFeed } from './feed-saga';
import { watchDataset } from './dataset-saga';

const rootSaga = function* (): Generator {
  yield all([watchAuth(), watchProfile(), watchFeed(), watchDataset()]);
};

export default rootSaga;

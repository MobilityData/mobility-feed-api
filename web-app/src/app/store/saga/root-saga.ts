import { all } from 'redux-saga/effects';
import { watchAuth } from './auth-saga';
import { watchProfile } from './profile-saga';
import { watchFeed } from './feed-saga';
import { watchDataset } from './dataset-saga';
import { watchFeeds } from './feeds-saga';
import { watchFetchFeedMetrics } from './analytics-saga';

const rootSaga = function* (): Generator {
  yield all([
    watchAuth(),
    watchProfile(),
    watchFeed(),
    watchDataset(),
    watchFeeds(),
    watchFetchFeedMetrics(),
  ]);
};

export default rootSaga;

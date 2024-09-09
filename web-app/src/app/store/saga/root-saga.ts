import { all } from 'redux-saga/effects';
import { watchAuth } from './auth-saga';
import { watchProfile } from './profile-saga';
import { watchFeed } from './feed-saga';
import { watchDataset } from './dataset-saga';
import { watchFeeds } from './feeds-saga';
import { watchGTFSFetchFeedMetrics } from './gtfs-analytics-saga';
import { watchGBFSFetchFeedMetrics } from './gbfs-analytics-saga';

const rootSaga = function* (): Generator {
  yield all([
    watchAuth(),
    watchProfile(),
    watchFeed(),
    watchDataset(),
    watchFeeds(),
    watchGTFSFetchFeedMetrics(),
    watchGBFSFetchFeedMetrics(),
  ]);
};

export default rootSaga;

import { combineReducers } from 'redux';
import profileReducer from './profile-reducer';
import feedReducer from './feed-reducer';
import datasetReducer from './dataset-reducer';
import feedsReducer from './feeds-reducer';
import GTFSAnalyticsReducer from './gtfs-analytics-reducer';
import GBFSAnalyticsReducer from './gbfs-analytics-reducer';
import supportingFilesReducer from './supporting-files-reducer';

const rootReducer = combineReducers({
  userProfile: profileReducer,
  feedProfile: feedReducer,
  dataset: datasetReducer,
  feeds: feedsReducer,
  gtfsAnalytics: GTFSAnalyticsReducer,
  gbfsAnalytics: GBFSAnalyticsReducer,
  supportingFiles: supportingFilesReducer,
});

export default rootReducer;

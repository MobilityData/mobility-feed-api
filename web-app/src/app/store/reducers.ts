import { combineReducers } from 'redux';
import profileReducer from './profile-reducer';
import feedReducer from './feed-reducer';
import datasetReducer from './dataset-reducer';

const rootReducer = combineReducers({
  userProfile: profileReducer,
  feedProfile: feedReducer,
  dataset: datasetReducer,
});

export default rootReducer;

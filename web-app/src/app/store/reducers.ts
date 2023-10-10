import { combineReducers } from 'redux';
import profileReducer from './profile-reducer';

const rootReducer = combineReducers({
  userProfile: profileReducer,
});

export default rootReducer;

import { type AllFeedsType } from '../services/feeds/utils';
import { type FeedStatus } from '../types';
import { type RootState } from './store';

export const selectFeedsData = (state: RootState): AllFeedsType | undefined => {
  return state.feeds.data;
};

export const selectFeedsStatus = (state: RootState): FeedStatus => {
  return state.feeds.status;
};

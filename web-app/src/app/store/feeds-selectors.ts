import { type AllFeedsType } from '../services/feeds/utils';
import { type RootState } from './store';

export const selectFeedsData = (state: RootState): AllFeedsType | undefined => {
  return state.feeds.data;
};

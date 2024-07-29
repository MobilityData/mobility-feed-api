import { type RootState } from './store';
import { type FeedMetrics } from '../screens/Analytics/types';

export const selectFeedMetrics = (state: RootState): FeedMetrics[] =>
  state.analytics.feedMetrics;
export const selectAnalyticsStatus = (state: RootState): string =>
  state.analytics.status;
export const selectAnalyticsError = (state: RootState): string | undefined =>
  state.analytics.error;

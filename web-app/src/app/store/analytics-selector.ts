import { type RootState } from './store';
import { type GTFSFeedMetrics } from '../screens/Analytics/types';

export const selectFeedMetrics = (state: RootState): GTFSFeedMetrics[] =>
  state.gtfsAnalytics.feedMetrics;
export const selectAnalyticsStatus = (state: RootState): string =>
  state.gtfsAnalytics.status;
export const selectAnalyticsError = (state: RootState): string | undefined =>
  state.gtfsAnalytics.error;

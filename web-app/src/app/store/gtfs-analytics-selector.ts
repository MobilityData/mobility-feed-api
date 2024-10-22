import { type RootState } from './store';
import { type GTFSFeedMetrics } from '../screens/Analytics/types';

export const selectGTFSFeedMetrics = (state: RootState): GTFSFeedMetrics[] =>
  state.gtfsAnalytics.feedMetrics;
export const selectGTFSAnalyticsStatus = (state: RootState): string =>
  state.gtfsAnalytics.status;
export const selectGTFSAnalyticsError = (
  state: RootState,
): string | undefined => state.gtfsAnalytics.error;

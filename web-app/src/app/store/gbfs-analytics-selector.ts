import { createSelector } from '@reduxjs/toolkit';
import { type RootState } from './store';
import { type GBFSFeedMetrics } from '../screens/Analytics/types';

// Selector to get the GBFS feed metrics
export const selectGBFSFeedMetrics = (state: RootState): GBFSFeedMetrics[] =>
  state.gbfsAnalytics.feedMetrics;

// Selector to get the status of the GBFS analytics
export const selectGBFSAnalyticsStatus = (
  state: RootState,
): 'loading' | 'loaded' | 'failed' => state.gbfsAnalytics.status;

// Selector to get any error messages from GBFS analytics
export const selectGBFSAnalyticsError = (
  state: RootState,
): string | undefined => state.gbfsAnalytics.error;

// Selector to get the list of available analytics files
export const selectAvailableGBFSFiles = createSelector(
  (state: RootState) => state.gbfsAnalytics.availableFiles,
  (availableFiles) => availableFiles,
);

// Selector to get the currently selected file
export const selectSelectedGBFSFile = createSelector(
  (state: RootState) => state.gbfsAnalytics.selectedFile,
  (selectedFile) => selectedFile,
);

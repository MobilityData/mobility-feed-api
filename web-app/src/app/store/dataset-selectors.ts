import { type LatLngExpression } from 'leaflet';
import { type components, type paths } from '../services/feeds/types';
import { type RootState } from './store';
import { createSelector } from '@reduxjs/toolkit';

export const selectDatasetsData = (
  state: RootState,
):
  | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
  | undefined => {
  return state.dataset.data;
};

export const selectDatasetsLoadingStatus = (
  state: RootState,
): 'loading' | 'loaded' => state.dataset.status;

export const selectLatestDatasetsData = (
  state: RootState,
): components['schemas']['GtfsDataset'] | undefined => {
  return state.dataset.data !== undefined ? state.dataset.data[0] : undefined;
};

export const selectBoundingBoxFromLatestDataset = createSelector(
  [selectLatestDatasetsData],
  (latestDataset): LatLngExpression[] | undefined => {
    if (latestDataset === undefined) return undefined;
    return latestDataset.bounding_box?.minimum_latitude !== undefined &&
      latestDataset.bounding_box?.maximum_latitude !== undefined &&
      latestDataset.bounding_box?.minimum_longitude !== undefined &&
      latestDataset.bounding_box?.maximum_longitude !== undefined
      ? [
          [
            latestDataset.bounding_box?.minimum_latitude,
            latestDataset.bounding_box?.minimum_longitude,
          ],
          [
            latestDataset.bounding_box?.minimum_latitude,
            latestDataset.bounding_box?.maximum_longitude,
          ],
          [
            latestDataset.bounding_box?.maximum_latitude,
            latestDataset.bounding_box?.maximum_longitude,
          ],
          [
            latestDataset.bounding_box?.maximum_latitude,
            latestDataset.bounding_box?.minimum_longitude,
          ],
        ]
      : undefined;
  },
);

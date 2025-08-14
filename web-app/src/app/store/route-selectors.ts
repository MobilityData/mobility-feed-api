import { type RootState } from './store';
import { type Route } from '../types/Route';

export const selectRoutes = (state: RootState): Route[] => state.routes.routes;
export const selectRoutesLoading = (state: RootState): boolean =>
  state.routes.loading;
export const selectRoutesError = (state: RootState): string | null =>
  state.routes.error;

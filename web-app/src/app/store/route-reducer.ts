import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type Route } from '../types/Route';

export interface RouteState {
  routes: Route[];
  loading: boolean;
  error: string | null;
}

const initialState: RouteState = {
  routes: [],
  loading: false,
  error: null,
};

export const routeSlice = createSlice({
  name: 'routes',
  initialState,
  reducers: {
    loadingRoutes: (
      state,
      action: PayloadAction<{ feedId: string; datasetId: string }>,
    ) => {
      state.loading = true;
      state.error = null;
    },
    routesLoaded: (state, action: PayloadAction<Route[]>) => {
      state.loading = false;
      state.routes = action.payload;
    },
    routesError: (state, action: PayloadAction<string>) => {
      state.loading = false;
      state.error = action.payload;
    },
  },
});

export const { loadingRoutes, routesLoaded, routesError } = routeSlice.actions;
export default routeSlice.reducer;

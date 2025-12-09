import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type LicenseErrors,
  LicenseErrorSource,
  type LicenseError,
} from '../types';
import { type components } from '../services/feeds/types';

export type License = components['schemas']['LicenseWithRules'];

interface LicenseState {
  status: 'loading' | 'loaded' | 'error';
  activeLicenseId: string | undefined;
  data: Record<string, { license: License; fetchedAt: number }>;
  errors: LicenseErrors;
}

const initialState: LicenseState = {
  status: 'loaded',
  activeLicenseId: undefined,
  data: {},
  errors: {
    [LicenseErrorSource.DatabaseAPI]: null,
  },
};

export const licenseSlice = createSlice({
  name: 'licenseProfile',
  initialState,
  reducers: {
    loadingLicense: (state, action: PayloadAction<{ licenseId: string }>) => {
      state.status = 'loading';
      state.activeLicenseId = action.payload.licenseId;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingLicenseSuccess: (
      state,
      action: PayloadAction<{ license: License; fetchedAt: number }>,
    ) => {
      state.status = 'loaded';
      if (action.payload.license.id) {
        state.data[action.payload.license.id] = {
          license: action.payload.license,
          fetchedAt: action.payload.fetchedAt,
        };
        state.activeLicenseId = action.payload.license.id;
      }
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
    loadingLicenseFail: (state, action: PayloadAction<LicenseError>) => {
      state.status = 'error';
      state.errors.DatabaseAPI = action.payload;
    },
    resetLicense: (state) => {
      state.status = 'loaded';
      state.activeLicenseId = undefined;
      state.errors = {
        ...state.errors,
        DatabaseAPI: initialState.errors.DatabaseAPI,
      };
    },
  },
});

export const {
  loadingLicense,
  loadingLicenseSuccess,
  loadingLicenseFail,
  resetLicense,
} = licenseSlice.actions;

export default licenseSlice.reducer;

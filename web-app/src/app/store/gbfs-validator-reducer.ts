import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { components } from '../services/feeds/gbfs-validator-types';

export type ValidationResult = components['schemas']['ValidationResult'];
export type BasicAuth = components['schemas']['BasicAuth'];
export type BearerTokenAuth = components['schemas']['BearerTokenAuth'];
export type OAuthClientCredentialsGrantAuth =
  components['schemas']['OAuthClientCredentialsGrantAuth'];

export type ValidateRequestBody =
  components['requestBodies']['ValidateRequestBody']['content']['application/json'];

interface GbfsValidatorState {
  loading: boolean;
  error?: string;
  result?: ValidationResult;
  lastParams?: ValidateRequestBody;
}

const initialState: GbfsValidatorState = {
  loading: false,
  error: undefined,
  result: undefined,
  lastParams: undefined,
};

const gbfsValidatorSlice = createSlice({
  name: 'gbfsValidator',
  initialState,
  reducers: {
    validateStart(state, action: PayloadAction<ValidateRequestBody>) {
      state.loading = true;
      state.error = undefined;
      state.lastParams = action.payload;
      state.result = undefined;
    },
    validateSuccess(state, action: PayloadAction<ValidationResult>) {
      state.loading = false;
      state.result = action.payload;
    },
    validateFailure(state, action: PayloadAction<string>) {
      state.loading = false;
      state.error = action.payload;
    },
    clear(state) {
      state.loading = false;
      state.error = undefined;
      state.result = undefined;
      state.lastParams = undefined;
    },
  },
});

export const { validateStart, validateSuccess, validateFailure, clear } =
  gbfsValidatorSlice.actions;

export default gbfsValidatorSlice.reducer;

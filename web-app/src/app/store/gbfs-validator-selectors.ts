import {
  type ValidateRequestBody,
  type ValidationResult,
} from './gbfs-validator-reducer';
import { type RootState } from './store';

export const selectGbfsValidationLoading = (state: RootState): boolean =>
  state.gbfsValidator.loading;

export const selectGbfsValidationError = (
  state: RootState,
): string | undefined => state.gbfsValidator.error;

export const selectGbfsValidationResult = (
  state: RootState,
): ValidationResult | undefined => state.gbfsValidator.result;

export const selectGbfsValidationParams = (
  state: RootState,
): ValidateRequestBody | undefined => state.gbfsValidator.lastParams;

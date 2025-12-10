import { type RootState } from './store';
import { type License } from './license-reducer';
import { type LicenseErrors } from '../types';

export const selectLicenseStatus = (
  state: RootState,
): 'loading' | 'loaded' | 'error' => state.licenseProfile.status;

export const selectActiveLicenseId = (state: RootState): string | undefined =>
  state.licenseProfile.activeLicenseId;

export const selectLicenseData = (
  state: RootState,
): Record<string, { license: License; fetchedAt: number }> =>
  state.licenseProfile.data;

export const selectActiveLicense = (state: RootState): License | undefined => {
  const activeId = state.licenseProfile.activeLicenseId;
  if (activeId == null || activeId === '') return undefined;
  return state.licenseProfile.data[activeId]?.license;
};

export const selectLicenseErrors = (state: RootState): LicenseErrors =>
  state.licenseProfile.errors;

import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import {
  type SupportingFileKey,
  type SupportingFile,
  type GeoJSONData,
  type GeoJSONDataGBFS,
  type GtfsRoute,
} from '../types';

type SupportingFilesState = {
  [K in SupportingFileKey]: SupportingFile;
};

// Top-level context to track which feed these supporting files belong to
interface SupportingFilesContext {
  feedId?: string;
  datasetId?: string;
  dataType?: string;
}

type FullSupportingFilesState = {
  context: SupportingFilesContext;
} & SupportingFilesState;

const initialState: FullSupportingFilesState = {
  context: {
    feedId: undefined,
    datasetId: undefined,
    dataType: undefined,
  },
  gtfsGeolocationGeojson: {
    key: 'gtfsGeolocationGeojson',
    status: 'uninitialized',
  },
  gtfsDatasetRoutesJson: {
    key: 'gtfsDatasetRoutesJson',
    status: 'uninitialized',
  },
};

export const supportingFilesSlice = createSlice({
  name: 'dataset',
  initialState,
  reducers: {
    clearSupportingFiles: (state) => {
      // Reset every supporting-file key to its initial value. Preserve the
      // context unless caller explicitly resets it via `setSupportingFilesContext`.
      const keys: Array<keyof SupportingFilesState> = [
        'gtfsGeolocationGeojson',
        'gtfsDatasetRoutesJson',
      ];
      keys.forEach((key) => {
        state[key] = initialState[key];
      });
    },
    // Set the current feed context for supporting files. When feedId changes
    // the saga will clear and reload supporting files for the new feed.
    setSupportingFilesContext: (
      state,
      action: PayloadAction<{ feedId?: string; dataType?: string }>,
    ) => {
      const { feedId, dataType } = action.payload ?? {};
      state.context.feedId = feedId;
      state.context.dataType = dataType;
    },
    loadingSupportingFile: (
      state,
      action: PayloadAction<{
        key: SupportingFileKey;
        url: string;
      }>,
    ) => {
      const { key } = action.payload;
      state[key].status = 'loading';
      state[key].data = initialState[key].data;
      state[key].error = initialState[key].error;
    },
    loadingSupportingFileSuccess: (
      state,
      action: PayloadAction<{
        data: GeoJSONData | GeoJSONDataGBFS | GtfsRoute[];
        key: SupportingFileKey;
      }>,
    ) => {
      const { key, data } = action.payload;
      state[key].status = 'loaded';
      state[key].data = data;
    },
    loadingSupportingFileFail: (
      state,
      action: PayloadAction<{ key: SupportingFileKey; error: string }>,
    ) => {
      const { key, error } = action.payload;
      state[key].error = error;
    },
  },
});

export const {
  clearSupportingFiles,
  setSupportingFilesContext,
  loadingSupportingFile,
  loadingSupportingFileSuccess,
  loadingSupportingFileFail,
} = supportingFilesSlice.actions;

export default supportingFilesSlice.reducer;

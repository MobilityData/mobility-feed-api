import { type paths } from '../services/feeds/types';
import { areAllDatasetsLoaded, mergeAndSortDatasets } from './dataset';

type Datasets =
  paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];

const newDatasets = [
  { id: 1, downloaded_at: '2023-01-02T00:00:00Z' },
  { id: 2, downloaded_at: '2023-02-01T00:00:00Z' },
] as unknown as Datasets;

const existingDatasets = [
  { id: 3, downloaded_at: '2023-01-12T00:00:00Z' },
  { id: 4, downloaded_at: '2023-03-01T00:00:00Z' },
] as unknown as Datasets;

const duplicateDatasets = [
  { id: 2, downloaded_at: '2023-02-01T00:00:00Z' },
  { id: 5, downloaded_at: '2023-05-12T00:00:00Z' },
] as unknown as Datasets;

describe('Dataset utils', () => {
  describe('mergeAndSortDatasets', () => {
    it('should return the sorted datasets when no existing datasets are provided', () => {
      const result = mergeAndSortDatasets(newDatasets, undefined);
      expect(result).toEqual([
        { id: 2, downloaded_at: '2023-02-01T00:00:00Z' },
        { id: 1, downloaded_at: '2023-01-02T00:00:00Z' },
      ]);
    });

    it('should return the merged and sorted datasets when existing datasets are provided', () => {
      const result = mergeAndSortDatasets(newDatasets, existingDatasets);
      expect(result).toEqual([
        { id: 3, downloaded_at: '2023-01-12T00:00:00Z' },
        { id: 4, downloaded_at: '2023-03-01T00:00:00Z' },
        { id: 2, downloaded_at: '2023-02-01T00:00:00Z' },
        { id: 1, downloaded_at: '2023-01-02T00:00:00Z' },
      ]);
    });

    it('should filter out duplicates and return the merged and sorted datasets', () => {
      const result = mergeAndSortDatasets(newDatasets, duplicateDatasets);
      expect(result).toEqual([
        { id: 2, downloaded_at: '2023-02-01T00:00:00Z' },
        { id: 5, downloaded_at: '2023-05-12T00:00:00Z' },
        { id: 1, downloaded_at: '2023-01-02T00:00:00Z' },
      ]);
    });
  });
  describe('areAllDatasetsLoaded', () => {
    it('should return true if offset and limit are undefined', () => {
      const result = areAllDatasetsLoaded(3, undefined, undefined);
      expect(result).toBe(true);
    });

    it('should return true if the number of datasets returned is less than the limit', () => {
      const result = areAllDatasetsLoaded(3, 5, undefined);
      expect(result).toBe(true);
    });

    it('should return undefined if offset is defined and limit is undefined', () => {
      const result = areAllDatasetsLoaded(3, undefined, 0);
      expect(result).toBe(undefined);
    });

    it('should return false if the number of datasets returned is greater than the limit', () => {
      const result = areAllDatasetsLoaded(3, 2, 5);
      expect(result).toBe(false);
    });
  });
});

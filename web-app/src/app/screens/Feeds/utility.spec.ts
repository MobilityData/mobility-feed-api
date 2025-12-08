import {
  getDataTypeParamFromSelectedFeedTypes,
  getInitialSelectedFeedTypes,
  parseQueryParamStatus,
} from './utility';

describe('utility.ts', () => {
  describe('getDataTypeParamFromSelectedFeedTypes', () => {
    test('returns gtfs when hasStatusFilters is true regardless of selection', () => {
      const selected = { gtfs: false, gtfs_rt: true, gbfs: true };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, true, true)).toBe(
        'gtfs',
      );
    });

    test('returns gtfs when hasStatusFilters is true even with GBFS disabled', () => {
      const selected = { gtfs: true, gtfs_rt: true, gbfs: false };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, true, false)).toBe(
        'gtfs',
      );
    });

    test('returns gtfs when only gtfs is selected and no status filters', () => {
      const selected = { gtfs: true, gtfs_rt: false, gbfs: false };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, false, true)).toBe(
        'gtfs',
      );
    });

    test('returns gtfs_rt when only gtfs_rt is selected and no status filters', () => {
      const selected = { gtfs: false, gtfs_rt: true, gbfs: false };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, false, true)).toBe(
        'gtfs_rt',
      );
    });

    test('returns gbfs when only gbfs is selected, GBFS enabled, and no status filters', () => {
      const selected = { gtfs: false, gtfs_rt: false, gbfs: true };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, false, true)).toBe(
        'gbfs',
      );
    });

    test('ignores gbfs when GBFS is disabled and no status filters', () => {
      const selected = { gtfs: false, gtfs_rt: false, gbfs: true };
      expect(
        getDataTypeParamFromSelectedFeedTypes(selected, false, false),
      ).toBe('gtfs,gtfs_rt');
    });

    test('returns combined gtfs,gtfs_rt when both selected and no status filters', () => {
      const selected = { gtfs: true, gtfs_rt: true, gbfs: false };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, false, true)).toBe(
        'gtfs,gtfs_rt',
      );
    });

    test('returns combined gtfs,gtfs_rt,gbfs when all selected, GBFS enabled, and no status filters', () => {
      const selected = { gtfs: true, gtfs_rt: true, gbfs: true };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, false, true)).toBe(
        'gtfs,gtfs_rt,gbfs',
      );
    });

    test('returns default all when none selected, GBFS enabled, and no status filters', () => {
      const selected = { gtfs: false, gtfs_rt: false, gbfs: false };
      expect(getDataTypeParamFromSelectedFeedTypes(selected, false, true)).toBe(
        'gtfs,gtfs_rt,gbfs',
      );
    });

    test('returns default gtfs,gtfs_rt when none selected, GBFS disabled, and no status filters', () => {
      const selected = { gtfs: false, gtfs_rt: false, gbfs: false };
      expect(
        getDataTypeParamFromSelectedFeedTypes(selected, false, false),
      ).toBe('gtfs,gtfs_rt');
    });

    test('returns only gtfs when gtfs selected, gbfs selected but disabled, and no status filters', () => {
      const selected = { gtfs: true, gtfs_rt: false, gbfs: true };
      expect(
        getDataTypeParamFromSelectedFeedTypes(selected, false, false),
      ).toBe('gtfs');
    });
  });

  describe('getInitialSelectedFeedTypes', () => {
    test('returns all false when no params provided', () => {
      const params = new URLSearchParams('');
      expect(getInitialSelectedFeedTypes(params)).toEqual({
        gtfs: false,
        gtfs_rt: false,
        gbfs: false,
      });
    });

    test('parses true/false correctly for each type', () => {
      const params = new URLSearchParams('gtfs=true&gtfs_rt=false&gbfs=true');
      expect(getInitialSelectedFeedTypes(params)).toEqual({
        gtfs: true,
        gtfs_rt: false,
        gbfs: true,
      });
    });

    test('missing params default to false (when any param present)', () => {
      const params = new URLSearchParams('gtfs=true');
      expect(getInitialSelectedFeedTypes(params)).toEqual({
        gtfs: true,
        gtfs_rt: false,
        gbfs: false,
      });
    });

    test('ignores invalid values', () => {
      const params = new URLSearchParams('gtfs=foo&gtfs_rt=bar&gbfs=baz');
      expect(getInitialSelectedFeedTypes(params)).toEqual({
        gtfs: false,
        gtfs_rt: false,
        gbfs: false,
      });
    });
  });

  describe('parseQueryParamStatus', () => {
    test('returns empty array when undefined', () => {
      expect(parseQueryParamStatus(undefined)).toEqual([]);
    });

    test('filters to allowed values', () => {
      expect(
        parseQueryParamStatus([
          'active',
          'deprecated',
          'inactive',
          'future',
          'development',
        ]),
      ).toEqual(['active', 'inactive', 'future']);
    });

    test('preserves order of valid inputs', () => {
      expect(parseQueryParamStatus(['future', 'active'])).toEqual([
        'future',
        'active',
      ]);
    });
  });
});

import {
  getPointerSegments,
  resolveJsonPointer,
  getMissingKeyFromMessage,
} from './errorDetailsUtils';

describe('errorDetailsUtils', () => {
  describe('getPointerSegments', () => {
    it('removes leading # and splits on /, filtering empty segments', () => {
      expect(getPointerSegments('#/a/b/c')).toEqual(['a', 'b', 'c']);
      expect(getPointerSegments('/a//b/')).toEqual(['a', 'b']);
      expect(getPointerSegments('#')).toEqual([]);
      expect(getPointerSegments('')).toEqual([]);
    });
  });

  describe('resolveJsonPointer', () => {
    // make the structure resemble GBFS feed JSON under /data
    const root = {
      data: {
        stations: [
          { station_id: 'S1', lat: 12.3 },
          { station_id: 'S2', lat: 45.6 },
        ],
        feeds: [{ name: 'primary' }, { name: 'secondary' }],
      },
      arr: [10, 20, 30],
      'tilde~key': 'tilde!',
      'slash/key': 'slash!',
      leaf: 'value',
    };

    it('resolves nested object and array pointers', () => {
      expect(resolveJsonPointer(root, '#/data/stations/0/station_id')).toBe(
        'S1',
      );
      expect(resolveJsonPointer(root, '#/data/stations/1/station_id')).toBe(
        'S2',
      );
      expect(resolveJsonPointer(root, '#/arr/2')).toBe(30);
    });

    it('returns undefined for out of range array index or invalid segment', () => {
      expect(resolveJsonPointer(root, '#/arr/10')).toBeUndefined();
      expect(
        resolveJsonPointer(root, '#/data/stations/x/name'),
      ).toBeUndefined();
    });

    it('handles ~1 (/) and ~0 (~) escape sequences', () => {
      // property named 'slash/key' must be referenced as 'slash~1key'
      expect(resolveJsonPointer(root, '#/slash~1key')).toBe('slash!');
      // property named 'tilde~key' must be referenced as 'tilde~0key'
      expect(resolveJsonPointer(root, '#/tilde~0key')).toBe('tilde!');
    });

    it('returns undefined when pointer descends past a primitive', () => {
      // 'station_id' is a string, so '/data/stations/0/station_id/x' should be undefined
      expect(
        resolveJsonPointer(root, '#/data/stations/0/station_id/x'),
      ).toBeUndefined();
    });
  });

  describe('getMissingKeyFromMessage', () => {
    it('extracts key name from standard message', () => {
      // GBFS-like messages
      expect(
        getMissingKeyFromMessage(
          '#/data/stations/0/items/2: required key [station_id] is missing',
        ),
      ).toBe('station_id');
      expect(getMissingKeyFromMessage('Required key [FEED_ID]')).toBe(
        'FEED_ID',
      );
      expect(
        getMissingKeyFromMessage(
          'validation error: required key [lat] not found in object',
        ),
      ).toBe('lat');
    });

    it('returns null when no match', () => {
      expect(getMissingKeyFromMessage('no required keys here')).toBeNull();
      expect(getMissingKeyFromMessage('requiredkey [x]')).toBeNull();
    });
  });
});

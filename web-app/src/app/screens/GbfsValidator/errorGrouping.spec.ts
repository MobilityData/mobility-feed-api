import { removePathFromMessage, groupErrorsByFile } from './errorGrouping';
import type { GbfsFile } from './errorGrouping';

describe('errorGrouping', () => {
  describe('removePathFromMessage', () => {
    it('removes exact path substrings from message and trims extra spaces', () => {
      const path = '/data/vehicle_types/14/default_pricing_plan_id';
      const message = `#/data/vehicle_types/14/default_pricing_plan_id: 1_47 is not a valid enum value`;
      const result = removePathFromMessage(message, path);
      // current implementation removes the path substring but leaves surrounding punctuation
      expect(result).toBe('#: 1_47 is not a valid enum value');
    });

    it('returns original message when path is empty', () => {
      const message = 'something went wrong';
      expect(removePathFromMessage(message, '')).toBe(message);
    });

    it('collapses multiple spaces after removal', () => {
      const path = '/foo/bar';
      const message = `prefix ${path}   :  detail`;
      const result = removePathFromMessage(message, path);
      // current implementation removes the path substring; surrounding text remains
      expect(result).toBe('prefix : detail');
    });
  });

  describe('groupErrorsByFile', () => {
    it('groups errors with same normalized path and same message', () => {
      // Use more realistic GBFS-like paths and messages so normalization intent is clear
      const files: GbfsFile[] = [
        {
          name: 'feed-stations.json',
          url: 'https://example.com/feed-stations.json',
          errors: [
            {
              instancePath: '/data/stations/8/items/2',
              message:
                '#/data/stations/8/items/2: missing required field "station_id"',
              keyword: 'required',
              schemaPath: '',
            },
            {
              instancePath: '/data/stations/9/items/3',
              message:
                '#/data/stations/9/items/3: missing required field "station_id"',
              keyword: 'required',
              schemaPath: '',
            },
          ],
          systemErrors: [],
        },
      ];

      const grouped = groupErrorsByFile(files);
      expect(grouped).toHaveLength(1);
      const gf = grouped[0];
      expect(gf.fileName).toBe('feed-stations.json');
      expect(gf.fileUrl).toBe('https://example.com/feed-stations.json');
      expect(gf.groups).toHaveLength(1);
      const group = gf.groups[0];
      // Normalization should replace numeric indices with '*' placeholders
      expect(group.normalizedPath).toBe('/data/stations/*/items/*');
      expect(group.occurrences).toHaveLength(2);
      expect(gf.total).toBe(2);
    });

    it('produces separate groups for different messages', () => {
      // Use GBFS-like paths but different messages so grouping splits by message
      const files: GbfsFile[] = [
        {
          name: 'feed-stations.json',
          url: 'https://example.com/feed-stations.json',
          errors: [
            {
              instancePath: '/data/stations/0/items/2',
              message:
                '#/data/stations/0/items/2: missing required field "station_id"',
              keyword: 'required',
              schemaPath: '',
            },
            {
              instancePath: '/data/stations/1/items/3',
              message:
                '#/data/stations/1/items/3: invalid type for field "lat"',
              keyword: 'type',
              schemaPath: '',
            },
          ],
          systemErrors: [],
        },
      ];

      const grouped = groupErrorsByFile(files);
      const gf = grouped[0];
      // two different messages -> two groups even though the normalized path is the same
      expect(gf.groups).toHaveLength(2);
      // each group should have 1 occurrence
      expect(
        gf.groups.map((g) => g.occurrences.length).sort((a, b) => a - b),
      ).toEqual([1, 1]);
    });

    it('handles files with no errors', () => {
      const files: GbfsFile[] = [
        { name: 'empty', errors: [], systemErrors: [] },
      ];
      const grouped = groupErrorsByFile(files);
      expect(grouped).toHaveLength(1);
      const gf = grouped[0];
      expect(gf.groups).toHaveLength(0);
      expect(gf.total).toBe(0);
    });

    it('passes through systemErrors and uses unknown for missing names', () => {
      const files: GbfsFile[] = [
        { systemErrors: [{ error: 'x', message: 'y' }] },
      ];
      const grouped = groupErrorsByFile(files);
      expect(grouped[0].fileName).toBe('unknown');
      expect(grouped[0].systemErrors).toHaveLength(1);
    });
  });
});

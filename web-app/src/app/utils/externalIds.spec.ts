import {
  filterFeedExternalIdsToSourceMap,
  externalIdSourceMap,
  type ExternalIdInfo,
} from './externalIds';

describe('filterFeedExternalIdsToSourceMap', () => {
  it('should keep only entries with known sources and external_id present', () => {
    const input = [
      { source: 'jbda', external_id: 'jbda-1-2' },
      { source: 'unknown', external_id: 'x' },
      { source: 'tld', external_id: 'tld-abc' },
    ];

    const out = filterFeedExternalIdsToSourceMap(input);
    expect(out).toHaveLength(2);
    expect(out).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: 'jbda', external_id: 'jbda-1-2' }),
        expect.objectContaining({ source: 'tld', external_id: 'tld-abc' }),
      ]),
    );
  });

  it('should be case-insensitive for source keys', () => {
    const input = [{ source: 'TLD', external_id: 'tld-1' }];
    const out = filterFeedExternalIdsToSourceMap(input);
    expect(out).toHaveLength(1);
    expect(out[0].source).toBe('TLD');
  });

  it('should exclude entries missing external_id', () => {
    const input = [
      { source: 'jbda', external_id: null },
      { source: 'jbda' },
      { source: 'jbda', external_id: 'jbda-5-6' },
    ] as unknown as ExternalIdInfo;
    const out = filterFeedExternalIdsToSourceMap(input);
    expect(out).toHaveLength(1);
    expect(out[0].external_id).toBe('jbda-5-6');
  });

  it('should return empty array when input is empty or no matches', () => {
    expect(filterFeedExternalIdsToSourceMap([])).toEqual([]);
    const input = [
      { source: 'unknown', external_id: 'x' },
      { source: 'also', external_id: 'y' },
    ];
    expect(filterFeedExternalIdsToSourceMap(input)).toEqual([]);
  });

  it('externalIdSourceMap should contain expected keys', () => {
    // ensure the map includes the keys we depend on
    expect(Object.keys(externalIdSourceMap)).toEqual(
      expect.arrayContaining(['jbda', 'tdg', 'ntd', 'tfs', 'tld']),
    );
  });
});

import { type GBFSVersionType } from '../../../services/feeds/utils';
import { sortGbfsVersions } from '../Feed.functions';
import { getGbfsFeatures } from './GbfsVersions';

describe('getGbfsFeatures', () => {
  it('returns an empty array if endpoints is undefined', () => {
    const input: GBFSVersionType = {};
    expect(getGbfsFeatures(input)).toEqual([]);
  });

  it('returns an empty array if no feature endpoints exist', () => {
    const input: GBFSVersionType = {
      endpoints: [
        { name: 'system_information', is_feature: false, language: 'en' },
        { name: 'station_information', is_feature: false, language: 'en' },
      ],
    };
    expect(getGbfsFeatures(input)).toEqual([]);
  });

  it('returns features from the language with the most feature endpoints', () => {
    const input: GBFSVersionType = {
      endpoints: [
        { name: 'feature1', is_feature: true, language: 'en' },
        { name: 'feature2', is_feature: true, language: 'en' },
        { name: 'feature3', is_feature: true, language: 'fr' },
      ],
    };
    expect(getGbfsFeatures(input)).toEqual([
      { name: 'feature1', is_feature: true, language: 'en' },
      { name: 'feature2', is_feature: true, language: 'en' },
    ]);
  });

  it('returns features from "no-lang" when language is null', () => {
    const input: GBFSVersionType = {
      endpoints: [
        { name: 'feature1', is_feature: true, language: undefined },
        { name: 'feature2', is_feature: true, language: undefined },
        { name: 'feature3', is_feature: true, language: 'en' },
      ],
    };
    expect(getGbfsFeatures(input)).toEqual([
      { name: 'feature1', is_feature: true, language: undefined },
      { name: 'feature2', is_feature: true, language: undefined },
    ]);
  });

  it('prefers "no-lang" if it has the most features', () => {
    const input: GBFSVersionType = {
      endpoints: [
        { name: 'feature1', is_feature: true, language: undefined },
        { name: 'feature2', is_feature: true, language: undefined },
        { name: 'feature3', is_feature: true, language: 'en' },
        { name: 'feature4', is_feature: true, language: 'en' },
      ],
    };
    expect(getGbfsFeatures(input)).toEqual([
      { name: 'feature1', is_feature: true, language: undefined },
      { name: 'feature2', is_feature: true, language: undefined },
    ]);
  });

  it('ignores endpoints with missing name or is_feature=false', () => {
    const input: GBFSVersionType = {
      endpoints: [
        { name: 'feature1', is_feature: true, language: 'en' },
        { name: undefined, is_feature: true, language: 'en' }, // ignored
        { name: 'feature2', is_feature: false, language: 'en' }, // ignored
        { name: 'feature3', is_feature: true, language: undefined },
      ],
    };
    expect(getGbfsFeatures(input)).toEqual([
      { name: 'feature1', is_feature: true, language: 'en' },
    ]);
  });

  it('returns an empty array if no endpoints meet the criteria', () => {
    const input: GBFSVersionType = {
      endpoints: [
        { name: undefined, is_feature: true, language: 'en' },
        { name: 'notAFeature', is_feature: false, language: 'en' },
        { name: 'anotherOne', is_feature: false, language: 'fr' },
      ],
    };
    expect(getGbfsFeatures(input)).toEqual([]);
  });
});

describe('sortGbfsVersions used with Array.sort()', () => {
  it('sorts versions descending numerically', () => {
    const versions: GBFSVersionType[] = [
      { version: '2.0' },
      { version: '1.1' },
      { version: '2.1' },
      { version: '1.0' },
    ];
    versions.sort(sortGbfsVersions);
    expect(versions).toEqual([
      { version: '2.1' },
      { version: '2.0' },
      { version: '1.1' },
      { version: '1.0' },
    ]);
  });

  it('handles missing versions (treated as 0)', () => {
    const versions: GBFSVersionType[] = [
      { version: '1.0' },
      { version: undefined },
      { version: '2.0' },
    ];
    versions.sort(sortGbfsVersions);
    expect(versions).toEqual([
      { version: '2.0' },
      { version: '1.0' },
      { version: undefined },
    ]);
  });

  it('handles versions with non-numeric characters', () => {
    const versions: GBFSVersionType[] = [
      { version: 'v2.0' },
      { version: 'v1.1-beta' },
      { version: 'v2.1-rc1' },
    ];
    versions.sort(sortGbfsVersions);
    expect(versions).toEqual([
      { version: 'v2.1-rc1' },
      { version: 'v2.0' },
      { version: 'v1.1-beta' },
    ]);
  });

  it('treats completely invalid versions as 0', () => {
    const versions: GBFSVersionType[] = [
      { version: 'invalid' },
      { version: '2.0' },
      { version: '1.0' },
    ];
    versions.sort(sortGbfsVersions);
    expect(versions).toEqual([
      { version: '2.0' },
      { version: '1.0' },
      { version: 'invalid' },
    ]);
  });

  it('treats identical versions as equal', () => {
    const versions: GBFSVersionType[] = [
      { version: '2.0' },
      { version: '2.0' },
      { version: '2.0' },
    ];
    versions.sort(sortGbfsVersions);
    expect(versions).toEqual([
      { version: '2.0' },
      { version: '2.0' },
      { version: '2.0' },
    ]);
  });

  it('prioritizes autodiscovery versions', () => {
    const versions: GBFSVersionType[] = [
      { version: '2.0', source: 'gbfs_versions' },
      { version: '2.0', source: 'autodiscovery' },
    ];
    versions.sort(sortGbfsVersions);
    expect(versions).toEqual([
      { version: '2.0', source: 'autodiscovery' },
      { version: '2.0', source: 'gbfs_versions' },
    ]);

    const versionsStable: GBFSVersionType[] = [
      { version: '2.0', source: 'autodiscovery' },
      { version: '2.0', source: 'gbfs_versions' },
    ];

    versionsStable.sort(sortGbfsVersions);
    expect(versionsStable).toEqual([
      { version: '2.0', source: 'autodiscovery' },
      { version: '2.0', source: 'gbfs_versions' },
    ]);

    const versionsAutoPriority: GBFSVersionType[] = [
      { version: '2.0', source: 'gbfs_versions' },
      { version: '3.0', source: 'gbfs_versions' },
      { version: '2.0', source: 'autodiscovery' },
    ];
    versionsAutoPriority.sort(sortGbfsVersions);
    expect(versionsAutoPriority).toEqual([
      { version: '3.0', source: 'gbfs_versions' },
      { version: '2.0', source: 'autodiscovery' },
      { version: '2.0', source: 'gbfs_versions' },
    ]);
  });
});

import {
  getCachedJson,
  setCachedJson,
  clearExpiredCaches,
} from './gbfsContextCache';

describe('gbfsContextCache', () => {
  const url = 'https://example.com/context.json';
  const key = `gbfs-context:${url}`;

  beforeEach(() => {
    localStorage.clear();
    jest.restoreAllMocks();
  });

  it('stores and retrieves JSON data via setCachedJson/getCachedJson', () => {
    const payload = { foo: 'bar', n: 42 } as const;
    setCachedJson(url, payload);

    const raw = localStorage.getItem(key);
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw as string);
    expect(parsed).toHaveProperty('ts');
    expect(parsed).toHaveProperty('data');

    const fetched = getCachedJson(url);
    expect(fetched).toEqual(payload);
  });

  it('returns null when no entry exists', () => {
    expect(getCachedJson('https://nope')).toBeNull();
  });

  it('returns null and removes expired entries on getCachedJson', () => {
    // expired timestamp (0)
    localStorage.setItem(key, JSON.stringify({ data: { a: 1 }, ts: 0 }));
    const fetched = getCachedJson(url);
    expect(fetched).toBeNull();
    // expired entry should be removed by getCachedJson
    expect(localStorage.getItem(key)).toBeNull();
  });

  it('returns null for corrupted JSON but does not remove it in getCachedJson', () => {
    localStorage.setItem(key, 'this-is-not-json');
    const fetched = getCachedJson(url);
    expect(fetched).toBeNull();
    // corrupted entry remains (getCachedJson only removes on invalid ts/expired)
    expect(localStorage.getItem(key)).toBe('this-is-not-json');
  });

  it('clearExpiredCaches removes corrupted and expired entries but keeps valid and non-prefixed keys', () => {
    const validKey = key;
    const expiredKey = `gbfs-context:${url}-expired`;
    const otherKey = 'some-other-key';

    const now = Date.now();
    // valid entry
    localStorage.setItem(
      validKey,
      JSON.stringify({ data: { ok: true }, ts: now }),
    );
    // expired entry
    localStorage.setItem(
      expiredKey,
      JSON.stringify({ data: { ok: false }, ts: 0 }),
    );
    // corrupted prefixed entry
    const corruptedKey = `gbfs-context:${url}-corrupt`;
    localStorage.setItem(corruptedKey, 'not-json');
    // non-prefixed entry
    localStorage.setItem(otherKey, 'keep-me');

    clearExpiredCaches();

    // valid should remain
    const validRaw = localStorage.getItem(validKey);
    expect(validRaw).not.toBeNull();
    // expired removed
    expect(localStorage.getItem(expiredKey)).toBeNull();
    // corrupted removed
    expect(localStorage.getItem(corruptedKey)).toBeNull();
    // other key untouched
    expect(localStorage.getItem(otherKey)).toBe('keep-me');
  });
});

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
    const root = {
      a: { b: [{ c: 1 }, { c: 2 }] },
      arr: [10, 20, 30],
      'tilde~key': 'tilde!',
      'slash/key': 'slash!',
      leaf: 'value',
    } as any;

    it('resolves nested object and array pointers', () => {
      expect(resolveJsonPointer(root, '#/a/b/0/c')).toBe(1);
      expect(resolveJsonPointer(root, '#/a/b/1/c')).toBe(2);
      expect(resolveJsonPointer(root, '#/arr/2')).toBe(30);
    });

    it('returns undefined for out of range array index or invalid segment', () => {
      expect(resolveJsonPointer(root, '#/arr/10')).toBeUndefined();
      expect(resolveJsonPointer(root, '#/a/b/x/c')).toBeUndefined();
    });

    it('handles ~1 (/) and ~0 (~) escape sequences', () => {
      // property named 'slash/key' must be referenced as 'slash~1key'
      expect(resolveJsonPointer(root, '#/slash~1key')).toBe('slash!');
      // property named 'tilde~key' must be referenced as 'tilde~0key'
      expect(resolveJsonPointer(root, '#/tilde~0key')).toBe('tilde!');
    });

    it('returns undefined when pointer descends past a primitive', () => {
      // 'leaf' is a string, so '/leaf/x' should be undefined
      expect(resolveJsonPointer(root, '#/leaf/x')).toBeUndefined();
    });
  });

  describe('getMissingKeyFromMessage', () => {
    it('extracts key name from standard message', () => {
      expect(getMissingKeyFromMessage('required key [name] is missing')).toBe(
        'name',
      );
      expect(getMissingKeyFromMessage('Required key [FOO]')).toBe('FOO');
      expect(
        getMissingKeyFromMessage('some text required key [bar] other'),
      ).toBe('bar');
    });

    it('returns null when no match', () => {
      expect(getMissingKeyFromMessage('no required keys here')).toBeNull();
      expect(getMissingKeyFromMessage('requiredkey [x]')).toBeNull();
    });
  });
});

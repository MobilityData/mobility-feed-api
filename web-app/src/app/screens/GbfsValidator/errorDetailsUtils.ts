export type JSONValue =
  | string
  | number
  | boolean
  | null
  | JSONValue[]
  | { [key: string]: JSONValue };

export function getPointerSegments(pointerRaw: string): string[] {
  const pointer = pointerRaw.startsWith('#') ? pointerRaw.slice(1) : pointerRaw;
  return pointer.split('/').filter((s) => s.length > 0);
}

export function resolveJsonPointer(
  root: JSONValue,
  pointerRaw: string,
): JSONValue | undefined {
  const segments = getPointerSegments(pointerRaw).map((seg) =>
    seg.replace(/~1/g, '/').replace(/~0/g, '~'),
  );
  let current: JSONValue | undefined = root;
  for (const seg of segments) {
    if (Array.isArray(current)) {
      const idx = Number(seg);
      if (Number.isNaN(idx) || idx < 0 || idx >= current.length)
        return undefined;
      current = current[idx];
    } else if (current !== null && typeof current === 'object') {
      current = current[seg];
    } else {
      return undefined;
    }
  }
  return current;
}

export function getMissingKeyFromMessage(msg: string): string | null {
  const m = msg.match(/required key\s*\[(.+?)\]/i);
  return m?.[1] ?? null;
}

import type { components } from '../../services/feeds/gbfs-validator-types';

export type GbfsFile = components['schemas']['GbfsFile'];
export type FileError = components['schemas']['FileError'];
export type SystemError = components['schemas']['SystemError'];

export interface GroupedError {
  key: string;
  normalizedPath: string;
  message: string;
  occurrences: Array<{ error: FileError }>;
}

export interface FileGroupedErrors {
  fileName: string;
  fileUrl?: string;
  groups: GroupedError[];
  total: number;
  systemErrors: SystemError[];
}

// Normalize an instancePath by replacing numeric indexes with '*', e.g. /stations/8/items/2 -> /stations/*/items/*
const normalizeInstancePath = (path: string): string =>
  path.replace(/\/(?:\d+)(?=\/|$)/g, '/*');

// Remove the instancePath substring from the message so identical errors differing only by index are grouped together
export const removePathFromMessage = (message: string, path: string): string =>
  message
    .split(path)
    .join('')
    .replace(/\s{2,}/g, ' ')
    .trim();

export function groupErrorsByFile(files: GbfsFile[]): FileGroupedErrors[] {
  return files.map((file) => {
    const errs = file.errors ?? [];
    const map = new Map<string, GroupedError>();
    for (const err of errs) {
      const path = err.instancePath ?? '';
      const normalizedPath = normalizeInstancePath(path);
      const msgNoPath = removePathFromMessage(err.message ?? '', path);
      const key = `${normalizedPath}::${msgNoPath}`;
      let group = map.get(key);
      if (group == undefined) {
        group = {
          key,
          normalizedPath,
          message: msgNoPath,
          occurrences: [],
        };
        map.set(key, group);
      }
      group.occurrences.push({ error: err });
    }
    const groups = Array.from(map.values()).sort(
      (a, b) => b.occurrences.length - a.occurrences.length,
    );
    return {
      fileName: file.name ?? 'unknown',
      fileUrl: file.url,
      groups,
      total: groups.reduce((acc, g) => acc + g.occurrences.length, 0),
      systemErrors: file.systemErrors ?? [],
    };
  });
}

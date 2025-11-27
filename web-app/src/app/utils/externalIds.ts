import { type components } from '../services/feeds/types';

export type ExternalIdInfo = components['schemas']['ExternalIds'];

export const externalIdSourceMap: Record<
  string,
  { label: string; translationKey: string }
> = {
  jbda: {
    label: 'JBDA',
    translationKey: 'externalIds.tooltips.jbda',
  },
  tdg: {
    label: 'TDG',
    translationKey: 'externalIds.tooltips.tdg',
  },
  ntd: {
    label: 'NTD',
    translationKey: 'externalIds.tooltips.ntd',
  },
  tfs: {
    label: 'TransitFeeds',
    translationKey: 'externalIds.tooltips.tfs',
  },
  tld: {
    label: 'Transit.land',
    translationKey: 'externalIds.tooltips.tld',
  },
};

export const filterFeedExternalIdsToSourceMap = (
  externalIds: ExternalIdInfo,
): Array<{ source: string; external_id: string }> => {
  return externalIds.filter(
    (id): id is { source: string; external_id: string } =>
      id?.source != null &&
      id?.external_id != null &&
      externalIdSourceMap[id.source.toLowerCase()] != undefined,
  );
};

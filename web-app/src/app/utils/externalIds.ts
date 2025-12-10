import { type components } from '../services/feeds/types';

export type ExternalIdInfo = components['schemas']['ExternalIds'];

export const externalIdSourceMap: Record<
  string,
  { label: string; translationKey: string; docsUrl?: string }
> = {
  jbda: {
    label: 'JBDA',
    translationKey: 'externalIds.tooltips.jbda',
    docsUrl: 'http://docs.gtfs-data.jp/api.v2.html',
  },
  tdg: {
    label: 'TDG',
    translationKey: 'externalIds.tooltips.tdg',
    docsUrl:
      'https://doc.transport.data.gouv.fr/outils/outils-disponibles-sur-le-pan/api',
  },
  ntd: {
    label: 'NTD',
    translationKey: 'externalIds.tooltips.ntd',
    docsUrl:
      'https://www.transit.dot.gov/ntd/data-product/2023-annual-database-general-transit-feed-specification-gtfs-weblinks',
  },
  tfs: {
    label: 'TransitFeeds',
    translationKey: 'externalIds.tooltips.tfs',
  },
  tld: {
    label: 'Transit.land',
    translationKey: 'externalIds.tooltips.tld',
    docsUrl: 'https://www.transit.land/documentation/rest-api/feeds',
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

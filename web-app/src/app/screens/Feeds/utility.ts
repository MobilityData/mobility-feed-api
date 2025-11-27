export type AllowedFeedSearchStatus = 'active' | 'inactive' | 'future';

export function getDataTypeParamFromSelectedFeedTypes(
  selectedFeedTypes: Record<string, boolean>,
  isGbfsEnabled: boolean,
): string | undefined {
  let dataTypeQueryParam = '';
  if (selectedFeedTypes.gtfs) {
    dataTypeQueryParam += 'gtfs';
  }
  if (selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam +=
      (dataTypeQueryParam.length > 0 ? ',' : '') + 'gtfs_rt';
  }
  if (selectedFeedTypes.gbfs && isGbfsEnabled) {
    dataTypeQueryParam += (dataTypeQueryParam.length > 0 ? ',' : '') + 'gbfs';
  }
  return dataTypeQueryParam.length > 0
    ? dataTypeQueryParam
    : isGbfsEnabled
      ? 'gtfs,gtfs_rt,gbfs'
      : 'gtfs,gtfs_rt';
}

export function getInitialSelectedFeedTypes(
  searchParams: URLSearchParams,
): Record<string, boolean> {
  const gtfsSearch = searchParams.get('gtfs');
  const gtfsRtSearch = searchParams.get('gtfs_rt');
  const gbfsSearch = searchParams.get('gbfs');

  if (gtfsSearch === null && gtfsRtSearch === null && gbfsSearch === null) {
    return {
      gtfs: false,
      gtfs_rt: false,
      gbfs: false,
    };
  } else {
    return {
      gtfs: gtfsSearch === 'true',
      gtfs_rt: gtfsRtSearch === 'true',
      gbfs: gbfsSearch === 'true',
    };
  }
}

export const parseQueryParamStatus = (
  queryStatus: string[] | undefined,
): AllowedFeedSearchStatus[] => {
  return (queryStatus?.filter((s) =>
    ['active', 'inactive', 'future'].includes(s),
  ) ?? []) as AllowedFeedSearchStatus[];
};

export function getDataTypeParamFromSelectedFeedTypes(
  selectedFeedTypes: Record<string, boolean>,
): string | undefined {
  let dataTypeQueryParam = '';
  if (selectedFeedTypes.gtfs) {
    dataTypeQueryParam += 'gtfs';
  }
  if (selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam +=
      (dataTypeQueryParam.length > 0 ? ',' : '') + 'gtfs_rt';
  }
  if (selectedFeedTypes.gbfs) {
    dataTypeQueryParam += (dataTypeQueryParam.length > 0 ? ',' : '') + 'gbfs';
  }
  return dataTypeQueryParam.length > 0
    ? dataTypeQueryParam
    : 'gtfs,gtfs_rt,gbfs';
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

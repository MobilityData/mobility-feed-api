export function getDataTypeParamFromSelectedFeedTypes(
  selectedFeedTypes: Record<string, boolean>,
): 'gtfs' | 'gtfs_rt' | undefined {
  let dataTypeQueryParam: 'gtfs' | 'gtfs_rt' | undefined;
  if (selectedFeedTypes.gtfs && !selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = 'gtfs';
  } else if (!selectedFeedTypes.gtfs && selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = 'gtfs_rt';
  } else if (!selectedFeedTypes.gtfs && !selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = undefined;
  }
  return dataTypeQueryParam;
}

export function getInitialSelectedFeedTypes(
  searchParams: URLSearchParams,
): Record<string, boolean> {
  const gtfsSearch = searchParams.get('gtfs');
  const gtfsRtSearch = searchParams.get('gtfs_rt');

  if (gtfsSearch === null && gtfsRtSearch === null) {
    return {
      gtfs: false,
      gtfs_rt: false,
    };
  } else {
    return {
      gtfs: gtfsSearch === 'true',
      gtfs_rt: gtfsRtSearch === 'true',
    };
  }
}

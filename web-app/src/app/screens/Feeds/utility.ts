export function getDataTypeParamFromSelectedFeedTypes(
  selectedFeedTypes: Record<string, boolean>,
): 'gtfs' | 'gtfs_rt' | 'gtfs,gtfs_rt' | 'gtfs,gtfs_rt,gbfs' | undefined {
  // TODO: Add support for GBFS feeds
  let dataTypeQueryParam: 'gtfs' | 'gtfs_rt' | 'gtfs,gtfs_rt' | 'gtfs,gtfs_rt,gbfs' | undefined;
  if (selectedFeedTypes.gtfs && !selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = 'gtfs';
  } else if (!selectedFeedTypes.gtfs && selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = 'gtfs_rt';
  } else {
    // Both GTFS and GTFS-RT are selected or none are selected
    dataTypeQueryParam = 'gtfs,gtfs_rt,gbfs'; // Temporarily filtering out GBFS feeds
  }
  return dataTypeQueryParam;
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

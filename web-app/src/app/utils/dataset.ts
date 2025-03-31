import { type paths } from '../services/feeds/types';

type Datasets =
  paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];

export function mergeAndSortDatasets(
  newDatasets: Datasets,
  existingDatasets: Datasets | undefined,
): Datasets {
  let formattedDatasets: Datasets = [];
  if (existingDatasets === undefined) {
    formattedDatasets = newDatasets.sort((a, b) => {
      if (a.downloaded_at !== undefined && b.downloaded_at !== undefined) {
        const dateB = new Date(b.downloaded_at).getTime();
        const dateA = new Date(a.downloaded_at).getTime();
        return dateB - dateA;
      }
      return 0;
    });
  } else {
    const existingIds = new Set(existingDatasets.map((item) => item.id));
    const newFilteredData = newDatasets.filter(
      (item) => !existingIds.has(item.id),
    );
    formattedDatasets = [...existingDatasets, ...newFilteredData].sort(
      (a, b) => {
        if (a.downloaded_at !== undefined && b.downloaded_at !== undefined) {
          const dateB = new Date(b.downloaded_at).getTime();
          const dateA = new Date(a.downloaded_at).getTime();
          return dateB - dateA;
        }
        return 0;
      },
    );
  }
  return formattedDatasets;
}

/*
 Function to determine if all datasets are loaded given the offset and limit
 False is if the datasets are not finished loading due to offset / limit
 True is if the datasets are all loaded for the given feed
 Undefined is if there is not enough information to determine if the datasets are all loaded
*/
export function areAllDatasetsLoaded(
  numberOfDatasetsLoaded: number,
  limit?: number,
  offset?: number,
): boolean | undefined {
  let hasLoadedAllData: boolean | undefined = false;
  if (offset == undefined && limit == undefined) {
    hasLoadedAllData = true;
  } else if (limit != undefined && numberOfDatasetsLoaded < limit) {
    hasLoadedAllData = true;
  } else if (offset != undefined && limit == undefined) {
    hasLoadedAllData = undefined;
  }
  return hasLoadedAllData;
}

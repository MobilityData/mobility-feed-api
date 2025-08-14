import { type Route } from '../../types/Route';
import { GET } from '../utils';

export const getRoutes = async (
  feedId: string,
  datasetId: string,
): Promise<Route[]> => {
  const response = await GET(
    `/v1/gtfs_feeds/${feedId}/datasets/${datasetId}/routes`,
  );
  return await response.json();
};

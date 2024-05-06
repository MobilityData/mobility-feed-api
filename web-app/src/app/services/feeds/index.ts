import createClient, { type Middleware } from 'openapi-fetch';
import type { paths } from './types';
import { type AllFeedType } from './utils';

const API_BASE_URL = 'https://api-dev.mobilitydatabase.org';

const client = createClient<paths>({ baseUrl: `${API_BASE_URL}` });

const throwOnError: Middleware = {
  async onResponse(res) {
    if (res.status >= 400) {
      let body = await res.clone().text();
      if (res.headers.get('content-type')?.includes('json') === true) {
        body = await res.clone().json();
      }
      throw new Error(body);
    }
    return undefined;
  },
};

client.use(throwOnError);

const generateAuthMiddlewareWithToken = (accessToken: string): Middleware => {
  return {
    async onRequest(req) {
      // add Authorization header to every request
      req.headers.set('Authorization', `Bearer ${accessToken}`);
      return req;
    },
  };
};

export const getFeeds = async (): Promise<
  | paths['/v1/feeds']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  return await client
    .GET('/v1/feeds', { params: {} })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    });
};

export const getFeed = async (
  feedId: string,
  accessToken: string,
): Promise<
  | paths['/v1/feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  const authMiddleware = generateAuthMiddlewareWithToken(accessToken);
  client.use(authMiddleware);
  return await client
    .GET('/v1/feeds/{id}', { params: { path: { id: feedId } } })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    })
    .finally(() => {
      client.eject(authMiddleware);
    });
};

export const getGtfsFeeds = async (): Promise<
  | paths['/v1/gtfs_feeds']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  return await client
    .GET('/v1/gtfs_feeds', { params: {} })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    });
};

export const getGtfsRtFeeds = async (): Promise<
  | paths['/v1/gtfs_rt_feeds']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  return await client
    .GET('/v1/gtfs_rt_feeds', { params: {} })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    });
};

export const getGtfsFeed = async (
  id: string,
  accessToken: string,
): Promise<AllFeedType> => {
  const authMiddleware = generateAuthMiddlewareWithToken(accessToken);
  client.use(authMiddleware);
  return await client
    .GET('/v1/gtfs_feeds/{id}', { params: { path: { id } } })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    })
    .finally(() => {
      client.eject(authMiddleware);
    });
};

export const getGtfsRtFeed = async (
  id: string,
  accessToken: string,
): Promise<
  | paths['/v1/gtfs_rt_feeds/{id}']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  const authMiddleware = generateAuthMiddlewareWithToken(accessToken);
  client.use(authMiddleware);
  return await client
    .GET('/v1/gtfs_rt_feeds/{id}', { params: { path: { id } } })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    })
    .finally(() => {
      client.eject(authMiddleware);
    });
};

export const getGtfsFeedDatasets = async (
  id: string,
  accessToken: string,
  queryParams?: paths['/v1/gtfs_feeds/{id}/datasets']['get']['parameters']['query'],
): Promise<
  | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  const authMiddleware = generateAuthMiddlewareWithToken(accessToken);
  client.use(authMiddleware);
  return await client
    .GET('/v1/gtfs_feeds/{id}/datasets', {
      params: { query: queryParams, path: { id } },
    })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    })
    .finally(() => {
      client.eject(authMiddleware);
    });
};

export const getDatasetGtfs = async (
  id: string,
  accessToken: string,
): Promise<
  | paths['/v1/datasets/gtfs/{id}']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  const authMiddleware = generateAuthMiddlewareWithToken(accessToken);
  client.use(authMiddleware);
  return await client
    .GET('/v1/datasets/gtfs/{id}', { params: { path: { id } } })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    })
    .finally(() => {
      client.eject(authMiddleware);
    });
};

export const getMetadata = async (): Promise<
  | paths['/v1/metadata']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  return await client
    .GET('/v1/metadata', { params: {} })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    });
};

export const searchFeeds = async (): Promise<
  | paths['/v1/search']['get']['responses'][200]['content']['application/json']
  | undefined
> => {
  return await client
    .GET('/v1/search', { params: {} })
    .then((response) => {
      const data = response.data;
      return data;
    })
    .catch(function (error) {
      throw error;
    });
};

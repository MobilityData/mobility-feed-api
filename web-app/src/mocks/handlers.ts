import { http, HttpResponse } from 'msw';

// Import fixtures
import feedJson from '../../cypress/fixtures/feed_test-516.json';
import gtfsFeedJson from '../../cypress/fixtures/gtfs_feed_test-516.json';
import datasetsFeedJson from '../../cypress/fixtures/feed_datasets_test-516.json';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_FEED_API_BASE_URL ||
  'https://api-dev.mobilitydatabase.org';

export const handlers = [
  // Mock GET /v1/feeds/{id} - basic feed info
  http.get(`${API_BASE_URL}/v1/feeds/test-516`, () => {
    return HttpResponse.json(feedJson);
  }),

  // Mock GET /v1/gtfs_feeds/{id} - GTFS specific feed info
  http.get(`${API_BASE_URL}/v1/gtfs_feeds/test-516`, () => {
    return HttpResponse.json(gtfsFeedJson);
  }),

  // Mock GET /v1/gtfs_feeds/{id}/datasets - feed datasets
  http.get(`${API_BASE_URL}/v1/gtfs_feeds/test-516/datasets`, () => {
    return HttpResponse.json(datasetsFeedJson);
  }),

  // Mock GET /v1/gtfs_feeds/{id}/gtfs_rt_feeds - associated GTFS-RT feeds
  http.get(`${API_BASE_URL}/v1/gtfs_feeds/test-516/gtfs_rt_feeds`, () => {
    return HttpResponse.json([]);
  }),

  // Mock routes endpoint for map visualization
  http.get(/.*test-516.*routes\.json$/, () => {
    return HttpResponse.json([]);
  }),
];

import * as React from 'react';
import { cache } from 'react';
import FeedView from '../../../screens/Feed/FeedView';
import {
  getFeed,
  getGtfsFeed,
  getGbfsFeed,
  getGtfsRtFeed,
  getGtfsFeedDatasets,
  getGtfsFeedRoutes,
  getGtfsFeedAssociatedGtfsRtFeeds,
} from '../../../services/feeds';
import { notFound } from 'next/navigation';
import type { Metadata, ResolvingMetadata } from 'next';
import { getSSRAccessToken } from '../../../utils/auth-server';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../../services/feeds/utils';
import {
  formatProvidersSorted,
  generatePageTitle,
  generateDescriptionMetaTag,
} from '../../../screens/Feed/Feed.functions';
import generateFeedStructuredData from '../../../screens/Feed/StructuredData.functions';
import { getTranslations } from 'next-intl/server';

interface Props {
  params: Promise<{ feedDataType: string; feedId: string }>;
}

const fetchFeedData = cache(
  async (feedDataType: string, feedId: string, accessToken: string) => {
    try {
      let feed;
      if (feedDataType === 'gtfs') {
        feed = await getGtfsFeed(feedId, accessToken);
      } else if (feedDataType === 'gtfs_rt') {
        feed = await getGtfsRtFeed(feedId, accessToken);
      } else if (feedDataType === 'gbfs') {
        feed = await getGbfsFeed(feedId, accessToken);
      } else {
        feed = await getFeed(feedId, accessToken);
      }
      return feed;
    } catch (e) {
      return undefined;
    }
  },
);

const fetchInitialDatasets = cache(
  async (feedId: string, accessToken: string) => {
    try {
      const datasets = await getGtfsFeedDatasets(feedId, accessToken, {
        limit: 10,
      });
      return datasets;
    } catch (e) {
      return [];
    }
  },
);

const fetchRelatedFeeds = cache(
  async (feedReferences: string[], accessToken: string) => {
    try {
      const feedPromises = feedReferences.map(
        async (feedId) =>
          await getFeed(feedId, accessToken).catch((e) => {
            return undefined;
          }),
      );
      const feeds = await Promise.all(feedPromises);
      // Filter out failed fetches and separate by type
      const validFeeds = feeds.filter((f) => f !== undefined);
      const gtfsFeeds = validFeeds.filter((f) => f?.data_type === 'gtfs');
      const gtfsRtFeeds = validFeeds.filter((f) => f?.data_type === 'gtfs_rt');
      return { gtfsFeeds, gtfsRtFeeds };
    } catch (e) {
      return { gtfsFeeds: [], gtfsRtFeeds: [] };
    }
  },
);

// TODO: extract this logic
const fetchRoutesData = cache(async (feedId: string, datasetId: string) => {
  try {
    const routes = await getGtfsFeedRoutes(feedId, datasetId);
    if (routes == null) {
      return { totalRoutes: undefined, routeTypes: undefined };
    }
    const totalRoutes = routes.length;
    // Extract unique route types and sort them
    const uniqueRouteTypesSet = new Set<string>();
    for (const route of routes) {
      const raw = route.routeType;
      const routeTypeStr = raw == null ? undefined : String(raw).trim();
      if (routeTypeStr != null) {
        uniqueRouteTypesSet.add(routeTypeStr);
      }
    }
    const routeTypes = Array.from(uniqueRouteTypesSet).sort((a, b) => {
      const validNumberA = a.trim() !== '' && Number.isFinite(Number(a));
      const validNumberB = b.trim() !== '' && Number.isFinite(Number(b));
      if (!validNumberA && !validNumberB) return a.localeCompare(b);
      if (!validNumberA || !validNumberB) return validNumberA ? -1 : 1;
      return Number(a) - Number(b);
    });
    return { totalRoutes, routeTypes };
  } catch (e) {
    return { totalRoutes: undefined, routeTypes: undefined };
  }
});

export async function generateMetadata(
  { params }: Props,
  parent: ResolvingMetadata,
): Promise<Metadata> {
  const { feedId, feedDataType } = await params;
  const accessToken = await getSSRAccessToken();
  const t = await getTranslations();

  const feed = await fetchFeedData(feedDataType, feedId, accessToken);

  if (feed == null) {
    return {
      title: 'Feed Not Found | Mobility Database',
    };
  }

  // Fetch related feeds for GTFS-RT to generate complete structured data
  const { gtfsFeeds, gtfsRtFeeds } =
    feedDataType === 'gtfs_rt' &&
    (feed as GTFSRTFeedType)?.feed_references != null
      ? await fetchRelatedFeeds(
          (feed as GTFSRTFeedType)?.feed_references ?? [],
          accessToken,
        )
      : { gtfsFeeds: [], gtfsRtFeeds: [] };

  const sortedProviders = formatProvidersSorted(feed?.provider ?? '');
  const title = generatePageTitle(
    sortedProviders,
    feed.data_type as 'gtfs' | 'gtfs_rt' | 'gbfs',
    (feed as { feed_name?: string })?.feed_name,
  );
  const description = generateDescriptionMetaTag(
    t,
    sortedProviders,
    feed.data_type as 'gtfs' | 'gtfs_rt' | 'gbfs',
    (feed as { feed_name?: string })?.feed_name,
  );

  // Generate structured data for SEO
  const structuredData = generateFeedStructuredData(
    feed,
    description,
    gtfsFeeds,
    gtfsRtFeeds,
  );

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://mobilitydatabase.org/feeds/${feedDataType}/${feedId}`,
      siteName: 'Mobility Database',
      type: 'website',
    },
    twitter: {
      card: 'summary',
      title,
      description,
    },
    alternates: {
      canonical: `/feeds/${feedDataType}/${feedId}`,
    },
    other: {
      // Structured data for JSON-LD
      ...(structuredData != null && {
        'script:ld+json': JSON.stringify(structuredData),
      }),
    },
  };
}

export default async function FeedPage({
  params,
}: Props): Promise<React.ReactElement> {
  const { feedId, feedDataType } = await params;
  const accessToken = await getSSRAccessToken();

  const feedPromise = fetchFeedData(feedDataType, feedId, accessToken);
  const datasetsPromise =
    feedDataType === 'gtfs'
      ? fetchInitialDatasets(feedId, accessToken)
      : Promise.resolve([]);

  const [feed, initialDatasets] = await Promise.all([
    feedPromise,
    datasetsPromise,
  ]);

  if (feed == null) {
    notFound();
  }

  let gtfsFeedsRelated: GTFSFeedType[] = [];
  let gtfsRtFeedsRelated: GTFSRTFeedType[] = [];
  if (feed.data_type === 'gtfs_rt') {
    const gtfsRtFeed: GTFSRTFeedType = feed;
    // TODO: optimize to avoid double fetching. Need a new endpoint
    const { gtfsFeeds, gtfsRtFeeds } = await fetchRelatedFeeds(
      gtfsRtFeed?.feed_references ?? [],
      accessToken,
    );

    const associatedGtfsRtFeedsArrays = await Promise.all(
      gtfsFeeds.map(
        async (gtfsFeed) =>
          await getGtfsFeedAssociatedGtfsRtFeeds(
            gtfsFeed?.id ?? '',
            accessToken,
          ),
      ),
    );
    gtfsFeedsRelated = gtfsFeeds;
    const allGtfsRtFeeds = [
      ...gtfsRtFeeds,
      ...associatedGtfsRtFeedsArrays.flat(),
    ];
    const uniqueGtfsRtFeedsMap = new Map();
    allGtfsRtFeeds.forEach((feedItem) => {
      if (feedItem?.id != null) {
        uniqueGtfsRtFeedsMap.set(feedItem.id, feedItem);
      }
    });
    gtfsRtFeedsRelated = Array.from(uniqueGtfsRtFeedsMap.values());
  }

  // Fetch routes data for GTFS feeds
  const { totalRoutes, routeTypes } =
    feedDataType === 'gtfs'
      ? await fetchRoutesData(
          feedId,
          (feed as GTFSFeedType)?.visualization_dataset_id ?? '',
        )
      : { totalRoutes: undefined, routeTypes: undefined };

  return (
    <FeedView
      feed={feed}
      feedDataType={feedDataType}
      initialDatasets={initialDatasets}
      relatedFeeds={gtfsFeedsRelated}
      relatedGtfsRtFeeds={gtfsRtFeedsRelated}
      totalRoutes={totalRoutes}
      routeTypes={routeTypes}
    />
  );
}

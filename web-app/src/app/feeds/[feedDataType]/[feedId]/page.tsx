import * as React from 'react';
import { cache } from 'react';
import FeedView from '../../../screens/Feed/FeedView';
import {
  getFeed,
  getGtfsFeed,
  getGbfsFeed,
  getGtfsRtFeed,
  getGtfsFeedDatasets,
} from '../../../services/feeds';
import { notFound } from 'next/navigation';
import type { Metadata, ResolvingMetadata } from 'next';
import { getSSRAccessToken } from '../../../utils/auth-server';
import { GTFSRTFeedType } from '../../../services/feeds/utils';
import {
  formatProvidersSorted,
  generatePageTitle,
  generateDescriptionMetaTag,
} from '../../../screens/Feed/Feed.functions';
import generateFeedStructuredData from '../../../screens/Feed/StructuredData.functions';
import { getTranslations } from 'next-intl/server';

type Props = {
  params: { feedDataType: string; feedId: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

const fetchFeedData = cache(
  async (feedDataType: string, feedId: string, accessToken: string) => {
    try {
      let feed = undefined;
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
      console.error('Error fetching feed', e);
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
      console.error('Error fetching initial datasets', e);
      return [];
    }
  },
);

const fetchRelatedFeeds = cache(
  async (feedReferences: string[], accessToken: string) => {
    try {
      const feedPromises = feedReferences.map((feedId) =>
        getFeed(feedId, accessToken).catch((e) => {
          console.error(`Error fetching feed ${feedId}`, e);
          return undefined;
        }),
      );
      const feeds = await Promise.all(feedPromises);
      // Filter out failed fetches and separate by type
      const validFeeds = feeds.filter((f) => f !== undefined);
      const gtfsFeeds = validFeeds.filter((f) => f.data_type === 'gtfs');
      const gtfsRtFeeds = validFeeds.filter((f) => f.data_type === 'gtfs_rt');
      return { gtfsFeeds, gtfsRtFeeds };
    } catch (e) {
      console.error('Error fetching related feeds', e);
      return { gtfsFeeds: [], gtfsRtFeeds: [] };
    }
  },
);

export async function generateMetadata(
  { params, searchParams }: Props,
  parent: ResolvingMetadata,
): Promise<Metadata> {
  const { feedId, feedDataType } = await params;
  const accessToken = await getSSRAccessToken();
  const t = await getTranslations();

  const feed = await fetchFeedData(feedDataType, feedId, accessToken);

  if (!feed) {
    return {
      title: 'Feed Not Found | Mobility Database',
    };
  }

  // Fetch related feeds for GTFS-RT to generate complete structured data
  const { gtfsFeeds, gtfsRtFeeds } =
    feedDataType === 'gtfs_rt' && (feed as GTFSRTFeedType)?.feed_references
      ? await fetchRelatedFeeds(
          (feed as GTFSRTFeedType)?.feed_references ?? [],
          accessToken,
        )
      : { gtfsFeeds: [], gtfsRtFeeds: [] };

  const sortedProviders = formatProvidersSorted(feed?.provider ?? '');
  const title = generatePageTitle(
    sortedProviders,
    feed.data_type as 'gtfs' | 'gtfs_rt' | 'gbfs',
    (feed as any)?.feed_name,
  );
  const description = generateDescriptionMetaTag(
    t,
    sortedProviders,
    feed.data_type as 'gtfs' | 'gtfs_rt' | 'gbfs',
    (feed as any)?.feed_name,
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
      ...(structuredData && {
        'script:ld+json': JSON.stringify(structuredData),
      }),
    },
  };
}

export default async function FeedPage({ params }: Props) {
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

  if (feed == undefined) {
    notFound();
  }

  const { gtfsFeeds, gtfsRtFeeds } = await (feedDataType === 'gtfs_rt' &&
  (feed as GTFSRTFeedType)?.feed_references
    ? fetchRelatedFeeds((feed as GTFSRTFeedType)?.feed_references ?? [], accessToken)
    : Promise.resolve({ gtfsFeeds: undefined, gtfsRtFeeds: undefined }));

  return (
    <FeedView
      feed={feed}
      feedDataType={feedDataType}
      initialDatasets={initialDatasets}
      relatedFeeds={gtfsFeeds}
      relatedGtfsRtFeeds={gtfsRtFeeds}
    />
  );
}
